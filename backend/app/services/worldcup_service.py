from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import logging
import time
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from redis import asyncio as redis_asyncio

from app.core.config import settings
from app.services.llm_registry import LLMRegistry, LLMProfileName

logger = logging.getLogger("uvicorn")

INITIAL_BANKROLL = 10000.0
PREKICK_ENTRY_WINDOW = timedelta(hours=2)

TEAM_ALIASES: Dict[str, List[str]] = {
    "United States": ["united states", "usa", "u.s.a", "u.s.", "usmnt"],
    "Bosnia-Herzegovina": ["bosnia-herzegovina", "bosnia and herzegovina", "bosnia herzegovina", "bih"],
    "South Korea": ["south korea", "korea republic", "korea"],
    "Czech Republic": ["czech republic", "czechia"],
}

STAGE_LABELS = {
    "Group Stage": "小组赛",
    "Round of 32": "32强",
    "Round of 16": "16强",
    "Quarterfinals": "8强",
    "Semifinals": "半决赛",
    "3rd-Place Match": "季军赛",
    "Final": "决赛",
}

_schedule_cache: Dict[str, Any] = {"expires_at": None, "matches": []}
_polymarket_cache: Dict[str, Any] = {"expires_at": None, "events": []}
_bankroll_ledger_cache: Dict[str, Any] = {"bets": []}
_ai_analysis_cache: Dict[str, Dict[str, Any]] = {}


class WorldCupService:
    _redis_client: Optional[redis_asyncio.Redis] = None
    _schedule_cache_key = "worldcup:schedule:v1"
    _polymarket_cache_key = "worldcup:polymarket:v2"
    _bankroll_ledger_key = "worldcup:bankroll:ledger:v1"
    _ai_analysis_cache_key_prefix = "worldcup:ai_analysis:"
    _matches_index_key = "worldcup:matches:index:v1"
    _match_key_prefix = "worldcup:match:v1:"
    _match_date_key_prefix = "worldcup:matches:date:v1:"
    _match_dates_index_key = "worldcup:matches:dates:v1"

    @staticmethod
    async def get_overview(refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            await WorldCupService._refresh_window_data()
        matches = await WorldCupService._load_matches()
        if not matches:
            matches = await WorldCupService._refresh_all_data()
        ledger = await WorldCupService._get_bankroll_ledger()
        bankroll_summary = WorldCupService._build_bankroll_summary(ledger)
        settled_matches = bankroll_summary["settled_matches"]
        open_positions = bankroll_summary["open_positions"]
        next_match_at = next(
            (match["kickoff_at"] for match in matches if match["status"] != "settled"),
            datetime.now(timezone.utc).isoformat(),
        )
        featured_matches = [WorldCupService._summary(match) for match in matches[:3]]
        market_ready_matches = sum(1 for match in matches if match["key_market"]["options"])
        total_matches = len(matches)
        # logger.info(
        #     "worldcup.get_overview refresh=%s matches=%s elapsed_ms=%.2f",
        #     refresh,
        #     total_matches,
        #     (time.perf_counter() - started_at) * 1000,
        # )

        return {
            "tournament": "2026 FIFA World Cup",
            "bankroll": bankroll_summary["bankroll"],
            "initial_bankroll": INITIAL_BANKROLL,
            "settled_matches": settled_matches,
            "open_positions": open_positions,
            "roi": bankroll_summary["roi"],
            "max_drawdown": bankroll_summary["max_drawdown"],
            "next_match_at": next_match_at,
            "phase_breakdown": WorldCupService._build_phase_breakdown(matches, ledger),
            "featured_matches": featured_matches,
            "bankroll_curve": bankroll_summary["bankroll_curve"],
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "market_heat": [
                {
                    "label": "已接市场覆盖率",
                    "value": round(market_ready_matches / total_matches * 100, 1) if total_matches else 0.0,
                },
                {
                    "label": "待同步盘口占比",
                    "value": round((total_matches - market_ready_matches) / total_matches * 100, 1) if total_matches else 0.0,
                },
                {
                    "label": "已完赛进度",
                    "value": round(settled_matches / total_matches * 100, 1) if total_matches else 0.0,
                },
            ],
        }

    @staticmethod
    async def run_daily_refresh() -> Dict[str, Any]:
        matches = await WorldCupService._refresh_all_data()
        return {
            "matches": len(matches),
            "settled": sum(1 for match in matches if match["status"] == "settled"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def run_prekick_sync() -> Dict[str, Any]:
        cached_matches = await WorldCupService._load_matches()
        if not cached_matches:
            cached_matches = await WorldCupService._refresh_all_data()
        ledger = await WorldCupService._get_bankroll_ledger()
        now = datetime.now(timezone.utc)
        relevant_matches = [
            match for match in cached_matches
            if WorldCupService._needs_prekick_attention(match, now=now)
        ]
        open_bets = [bet for bet in ledger if bet.get("status") == "open"]
        if not relevant_matches and not open_bets:
            return {
                "skipped": True,
                "reason": "no_matches_in_window",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        refresh_match_ids = [match["match_id"] for match in relevant_matches]
        refresh_match_ids.extend(str(bet.get("match_id")) for bet in open_bets if bet.get("match_id"))
        matches = await WorldCupService._refresh_window_data(match_ids=refresh_match_ids)
        updated_ledger = await WorldCupService._get_bankroll_ledger()
        return {
            "skipped": False,
            "matches": len(matches),
            "window_matches": sum(
                1 for match in matches if WorldCupService._needs_prekick_attention(match, now=datetime.now(timezone.utc))
            ),
            "open_bets": sum(1 for bet in updated_ledger if bet.get("status") == "open"),
            "settled_bets": sum(1 for bet in updated_ledger if WorldCupService._is_bet_closed(bet)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def list_matches(stage: Optional[str] = None, status: Optional[str] = None, refresh: bool = False) -> List[Dict[str, Any]]:
        if refresh:
            await WorldCupService._refresh_window_data()
        matches = await WorldCupService._load_matches()
        if not matches:
            matches = await WorldCupService._refresh_all_data()
        if stage:
            matches = [match for match in matches if match["stage"] == stage]
        if status:
            matches = [match for match in matches if match["status"] == status]
        return [WorldCupService._summary(match) for match in matches]

    @staticmethod
    async def get_match_detail(match_id: str, refresh: bool = False, ai_refresh: bool = False) -> Optional[Dict[str, Any]]:
        if refresh:
            await WorldCupService._refresh_match_data(match_id)
        match = await WorldCupService._get_stored_match(match_id)
        if not match:
            matches = await WorldCupService._load_matches()
            if not matches:
                await WorldCupService._refresh_all_data()
                match = await WorldCupService._get_stored_match(match_id)
            else:
                match = next((item for item in matches if item["match_id"] == match_id), None)
        if not match:
            return None
        detail = deepcopy(match)
        ledger = await WorldCupService._get_bankroll_ledger()
        bet = next((item for item in ledger if str(item.get("match_id")) == match_id), None)
        detail["bankroll_bet"] = WorldCupService._serialize_bankroll_bet(bet)
        detail["ai_analysis"] = None
        detail["ai_analysis_error"] = None
        try:
            detail["ai_analysis"] = await WorldCupService._get_ai_analysis(detail, refresh=refresh or ai_refresh)
        except Exception as exc:
            detail["ai_analysis_error"] = str(exc) or "AI 解读生成失败"
        return detail

    @staticmethod
    async def _load_matches() -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        expires_at = _schedule_cache["expires_at"]
        if expires_at and expires_at > now and _schedule_cache["matches"]:
            return deepcopy(_schedule_cache["matches"])

        matches = await WorldCupService._load_stored_matches()
        if matches:
            _schedule_cache["matches"] = deepcopy(matches)
            _schedule_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
            return matches

        migrated = await WorldCupService._migrate_legacy_schedule_cache()
        if migrated:
            _schedule_cache["matches"] = deepcopy(migrated)
            _schedule_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
        return migrated

    @classmethod
    def _match_key(cls, match_id: str) -> str:
        return f"{cls._match_key_prefix}{match_id}"

    @classmethod
    def _match_date_key(cls, date_key: str) -> str:
        return f"{cls._match_date_key_prefix}{date_key}"

    @staticmethod
    def _kickoff_date_key(kickoff_at: Optional[str]) -> Optional[str]:
        if not kickoff_at:
            return None
        try:
            kickoff_dt = datetime.fromisoformat(str(kickoff_at).replace("Z", "+00:00"))
        except ValueError:
            return None
        return kickoff_dt.date().isoformat()

    @staticmethod
    def _date_point_to_key(day: str) -> str:
        return f"{day[:4]}-{day[4:6]}-{day[6:8]}"

    @staticmethod
    def _date_key_to_point(day: str) -> str:
        return day.replace("-", "")

    @staticmethod
    def _window_date_points(now: Optional[datetime] = None) -> List[str]:
        anchor = now or datetime.now(timezone.utc)
        return [
            (anchor.date() + timedelta(days=offset)).strftime("%Y%m%d")
            for offset in (-1, 0, 1)
        ]

    @classmethod
    async def _get_json_value(cls, key: str) -> Any:
        try:
            payload = await cls._get_redis_client().get(key)
            if not payload:
                return None
            return json.loads(payload)
        except Exception:
            return None

    @classmethod
    async def _set_json_value(cls, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        try:
            kwargs: Dict[str, Any] = {}
            if ttl_seconds:
                kwargs["ex"] = ttl_seconds
            await cls._get_redis_client().set(
                key,
                json.dumps(value, ensure_ascii=False),
                **kwargs,
            )
        except Exception:
            return None

    @classmethod
    async def _load_stored_matches(cls) -> List[Dict[str, Any]]:
        index = await cls._get_json_value(cls._matches_index_key)
        if not isinstance(index, list) or not index:
            return []
        matches: List[Dict[str, Any]] = []
        for match_id in index:
            match = await cls._get_json_value(cls._match_key(str(match_id)))
            if isinstance(match, dict):
                matches.append(match)
        matches.sort(key=WorldCupService._sort_key)
        return matches

    @classmethod
    async def _load_stored_matches_by_ids(cls, match_ids: List[str]) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        seen = set()
        for match_id in match_ids:
            normalized = str(match_id)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            match = await cls._get_json_value(cls._match_key(normalized))
            if isinstance(match, dict):
                matches.append(match)
        matches.sort(key=WorldCupService._sort_key)
        return matches

    @classmethod
    async def _get_stored_match(cls, match_id: str) -> Optional[Dict[str, Any]]:
        match = await cls._get_json_value(cls._match_key(str(match_id)))
        if isinstance(match, dict):
            return match
        return None

    @classmethod
    async def _load_stored_matches_for_dates(cls, date_keys: List[str]) -> List[Dict[str, Any]]:
        match_ids: List[str] = []
        for date_key in date_keys:
            ids = await cls._get_json_value(cls._match_date_key(date_key))
            if isinstance(ids, list):
                match_ids.extend(str(item) for item in ids)
        return await cls._load_stored_matches_by_ids(match_ids)

    @classmethod
    async def _store_matches(
        cls,
        matches: List[Dict[str, Any]],
        date_replacements: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        full_replace: bool = False,
    ) -> None:
        if not matches and not date_replacements and not full_replace:
            return

        redis_client = cls._get_redis_client()
        existing_index_raw = await cls._get_json_value(cls._matches_index_key)
        existing_index = {str(item) for item in existing_index_raw} if isinstance(existing_index_raw, list) else set()
        for match in matches:
            await redis_client.set(
                cls._match_key(str(match["match_id"])),
                json.dumps(match, ensure_ascii=False),
            )

        if full_replace:
            new_index = {str(match["match_id"]) for match in matches}
            stale_match_keys = [cls._match_key(match_id) for match_id in (existing_index - new_index)]
            if stale_match_keys:
                await redis_client.delete(*stale_match_keys)
            all_dates = await cls._get_json_value(cls._match_dates_index_key)
            if isinstance(all_dates, list):
                old_date_keys = [cls._match_date_key(str(item)) for item in all_dates]
                if old_date_keys:
                    await redis_client.delete(*old_date_keys)
            grouped: Dict[str, List[str]] = {}
            for match in matches:
                date_key = cls._kickoff_date_key(match.get("kickoff_at"))
                if not date_key:
                    continue
                grouped.setdefault(date_key, []).append(str(match["match_id"]))
            for date_key, match_ids in grouped.items():
                await redis_client.set(
                    cls._match_date_key(date_key),
                    json.dumps(match_ids, ensure_ascii=False),
                )
            await redis_client.set(
                cls._match_dates_index_key,
                json.dumps(sorted(grouped.keys()), ensure_ascii=False),
            )
        elif date_replacements:
            known_dates_raw = await cls._get_json_value(cls._match_dates_index_key)
            known_dates = set(str(item) for item in known_dates_raw) if isinstance(known_dates_raw, list) else set()
            for date_key, date_matches in date_replacements.items():
                match_ids = [str(match["match_id"]) for match in date_matches]
                await redis_client.set(
                    cls._match_date_key(date_key),
                    json.dumps(match_ids, ensure_ascii=False),
                )
                known_dates.add(date_key)
            await redis_client.set(
                cls._match_dates_index_key,
                json.dumps(sorted(known_dates), ensure_ascii=False),
            )

        index = sorted({str(match["match_id"]) for match in matches}, key=str)
        await redis_client.set(
            cls._matches_index_key,
            json.dumps(index, ensure_ascii=False),
        )
        _schedule_cache["matches"] = deepcopy(sorted(matches, key=WorldCupService._sort_key))
        _schedule_cache["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)

    @classmethod
    async def _migrate_legacy_schedule_cache(cls) -> List[Dict[str, Any]]:
        cached_matches = await cls._get_cached_json(cls._schedule_cache_key)
        if not cached_matches:
            return []
        await cls._store_matches(cached_matches, full_replace=True)
        return cached_matches

    @staticmethod
    def _merge_preserved_match_state(fresh_match: Dict[str, Any], existing_match: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not existing_match:
            return fresh_match
        merged = deepcopy(fresh_match)
        for field in ("featured_pick", "key_market", "markets", "line_movement", "polymarket_probabilities"):
            if existing_match.get(field):
                merged[field] = deepcopy(existing_match[field])
        if existing_match.get("source") == "polymarket_live" and merged.get("source") == "espn_schedule":
            merged["source"] = existing_match.get("source")
        if existing_match.get("external_url") and not merged.get("external_url"):
            merged["external_url"] = existing_match.get("external_url")
        return merged

    @classmethod
    async def _fetch_schedule_slice(cls, date_points: List[str]) -> Dict[str, Optional[List[Dict[str, Any]]]]:
        if not date_points:
            return {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [cls._fetch_schedule_day(client, day) for day in date_points]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        schedule_by_day: Dict[str, Optional[List[Dict[str, Any]]]] = {}
        for day, response in zip(date_points, responses):
            if isinstance(response, Exception):
                logger.warning("worldcup.schedule_slice day=%s failed=%s", day, response.__class__.__name__)
                schedule_by_day[day] = None
                continue
            if response is None:
                schedule_by_day[day] = None
                continue
            mapped_matches = [cls._map_espn_event(event) for event in response]
            schedule_by_day[day] = [match for match in mapped_matches if match]
        return schedule_by_day

    @classmethod
    async def _refresh_dates(cls, date_points: List[str], polymarket_refresh: bool = True) -> List[Dict[str, Any]]:
        date_points = sorted({day for day in date_points if day})
        if not date_points:
            return await cls._load_matches()

        date_keys = [cls._date_point_to_key(day) for day in date_points]
        existing_matches = await cls._load_stored_matches_for_dates(date_keys)
        existing_by_id = {str(match["match_id"]): match for match in existing_matches}
        existing_by_date: Dict[str, List[Dict[str, Any]]] = {date_key: [] for date_key in date_keys}
        for match in existing_matches:
            date_key = cls._kickoff_date_key(match.get("kickoff_at"))
            if date_key:
                existing_by_date.setdefault(date_key, []).append(match)

        fetched_by_day = await cls._fetch_schedule_slice(date_points)
        updated_by_date: Dict[str, List[Dict[str, Any]]] = {}
        updated_matches: List[Dict[str, Any]] = []
        for date_point in date_points:
            date_key = cls._date_point_to_key(date_point)
            day_matches = fetched_by_day.get(date_point)
            if day_matches is None:
                updated_by_date[date_key] = deepcopy(existing_by_date.get(date_key, []))
                updated_matches.extend(updated_by_date[date_key])
                continue
            merged_matches = [
                cls._merge_preserved_match_state(match, existing_by_id.get(str(match["match_id"])))
                for match in day_matches
            ]
            updated_by_date[date_key] = merged_matches
            updated_matches.extend(merged_matches)

        if settings.WORLDCUP_POLYMARKET_ENABLED:
            events = await cls._fetch_polymarket_events(refresh=polymarket_refresh)
            if events:
                for match in updated_matches:
                    event = cls._match_polymarket_event(match, events)
                    if event:
                        cls._apply_polymarket_event(match, event)

        all_matches = await cls._load_matches()
        retained_matches = [
            match for match in all_matches
            if cls._kickoff_date_key(match.get("kickoff_at")) not in updated_by_date
        ]
        merged_all_matches = retained_matches + updated_matches
        merged_all_matches.sort(key=WorldCupService._sort_key)

        await cls._store_matches(merged_all_matches, date_replacements=updated_by_date)
        await cls._sync_bankroll_ledger(updated_matches)
        return merged_all_matches

    @classmethod
    async def _refresh_all_data(cls) -> List[Dict[str, Any]]:
        start = date.fromisoformat(settings.WORLDCUP_SCHEDULE_START_DATE)
        end = date.fromisoformat(settings.WORLDCUP_SCHEDULE_END_DATE)
        date_points = []
        cursor = start
        while cursor <= end:
            date_points.append(cursor.strftime("%Y%m%d"))
            cursor += timedelta(days=1)
        matches = await cls._refresh_dates(date_points, polymarket_refresh=True)
        await cls._store_matches(matches, full_replace=True)
        return matches

    @classmethod
    async def _refresh_window_data(cls, match_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        date_points = set(cls._window_date_points())
        if match_ids:
            related_matches = await cls._load_stored_matches_by_ids([str(match_id) for match_id in match_ids])
            for match in related_matches:
                date_key = cls._kickoff_date_key(match.get("kickoff_at"))
                if date_key:
                    date_points.add(cls._date_key_to_point(date_key))
        return await cls._refresh_dates(sorted(date_points), polymarket_refresh=True)

    @classmethod
    async def _refresh_match_data(cls, match_id: str) -> Optional[Dict[str, Any]]:
        match = await cls._get_stored_match(match_id)
        if not match:
            matches = await cls._refresh_all_data()
            return next((item for item in matches if item["match_id"] == match_id), None)
        date_key = cls._kickoff_date_key(match.get("kickoff_at"))
        if not date_key:
            return match
        await cls._refresh_dates([cls._date_key_to_point(date_key)], polymarket_refresh=True)
        return await cls._get_stored_match(match_id)

    @staticmethod
    async def _fetch_schedule_matches(refresh: bool = False) -> List[Dict[str, Any]]:
        started_at = time.perf_counter()
        now = datetime.now(timezone.utc)
        expires_at = _schedule_cache["expires_at"]
        if not refresh and expires_at and expires_at > now:
            # logger.info(
            #     "worldcup.schedule_cache hit=memory matches=%s elapsed_ms=%.2f",
            #     len(_schedule_cache["matches"]),
            #     (time.perf_counter() - started_at) * 1000,
            # )
            return deepcopy(_schedule_cache["matches"])

        if not refresh:
            redis_started_at = time.perf_counter()
            cached_matches = await WorldCupService._get_cached_json(WorldCupService._schedule_cache_key)
            # logger.info(
            #     "worldcup.schedule_cache redis_lookup hit=%s elapsed_ms=%.2f",
            #     bool(cached_matches),
            #     (time.perf_counter() - redis_started_at) * 1000,
            # )
            if cached_matches:
                _schedule_cache["matches"] = deepcopy(cached_matches)
                _schedule_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
                # logger.info(
                #     "worldcup.schedule_cache hit=redis matches=%s elapsed_ms=%.2f",
                #     len(cached_matches),
                #     (time.perf_counter() - started_at) * 1000,
                # )
                return cached_matches

        start = date.fromisoformat(settings.WORLDCUP_SCHEDULE_START_DATE)
        end = date.fromisoformat(settings.WORLDCUP_SCHEDULE_END_DATE)
        date_points = []
        cursor = start
        while cursor <= end:
            date_points.append(cursor.strftime("%Y%m%d"))
            cursor += timedelta(days=1)

        fetch_started_at = time.perf_counter()
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [WorldCupService._fetch_schedule_day(client, day) for day in date_points]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        exception_count = sum(1 for item in responses if isinstance(item, Exception))
        logger.info(
            "worldcup.schedule_fetch dates=%s exceptions=%s elapsed_ms=%.2f",
            len(date_points),
            exception_count,
            (time.perf_counter() - fetch_started_at) * 1000,
        )

        events_by_id: Dict[str, Dict[str, Any]] = {}
        response_list_count = 0
        for item in responses:
            if isinstance(item, list):
                response_list_count += 1
                for event in item:
                    event_id = str(event.get("id", ""))
                    if event_id:
                        events_by_id[event_id] = event
            elif isinstance(item, Exception):
                logger.warning(
                    "worldcup.schedule_fetch task_failed=%s elapsed_ms=%.2f",
                    item.__class__.__name__,
                    (time.perf_counter() - started_at) * 1000,
                )

        map_started_at = time.perf_counter()
        matches = [WorldCupService._map_espn_event(event) for event in events_by_id.values()]
        matches = [match for match in matches if match]
        matches.sort(key=WorldCupService._sort_key)
        logger.info(
            "worldcup.schedule_map response_lists=%s events=%s matches=%s elapsed_ms=%.2f",
            response_list_count,
            len(events_by_id),
            len(matches),
            (time.perf_counter() - map_started_at) * 1000,
        )

        _schedule_cache["matches"] = deepcopy(matches)
        _schedule_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
        redis_store_started_at = time.perf_counter()
        await WorldCupService._set_cached_json(
            WorldCupService._schedule_cache_key,
            matches,
            settings.WORLDCUP_SCHEDULE_CACHE_SECONDS,
        )
        # logger.info(
        #     "worldcup.schedule_cache store=redis matches=%s elapsed_ms=%.2f total_elapsed_ms=%.2f",
        #     len(matches),
        #     (time.perf_counter() - redis_store_started_at) * 1000,
        #     (time.perf_counter() - started_at) * 1000,
        # )
        return matches

    @staticmethod
    async def _fetch_schedule_day(client: httpx.AsyncClient, day: str) -> Optional[List[Dict[str, Any]]]:
        started_at = time.perf_counter()
        try:
            response = await client.get(
                f"{settings.WORLDCUP_SCHEDULE_API_BASE}/scoreboard",
                params={"dates": day},
            )
            response.raise_for_status()
            payload = response.json()
            events = payload.get("events")
            if isinstance(events, list):
                logger.info(
                    "worldcup.schedule_day day=%s events=%s elapsed_ms=%.2f",
                    day,
                    len(events),
                    (time.perf_counter() - started_at) * 1000,
                )
                return events
        except Exception as exc:
            logger.warning(
                "worldcup.schedule_day day=%s failed=%s detail=%s elapsed_ms=%.2f",
                day,
                exc.__class__.__name__,
                exc,
                (time.perf_counter() - started_at) * 1000,
            )
            return None
        logger.warning(
            "worldcup.schedule_day day=%s empty_payload elapsed_ms=%.2f",
            day,
            (time.perf_counter() - started_at) * 1000,
        )
        return []

    @staticmethod
    async def _fetch_polymarket_events(refresh: bool = False) -> List[Dict[str, Any]]:
        started_at = time.perf_counter()
        now = datetime.now(timezone.utc)
        logger.info(
            "worldcup.polymarket_cache begin refresh=%s memory_events=%s redis_key=%s",
            refresh,
            len(_polymarket_cache["events"]),
            WorldCupService._polymarket_cache_key,
        )
        expires_at = _polymarket_cache["expires_at"]
        if not refresh and expires_at and expires_at > now:
            logger.info(
                "worldcup.polymarket_cache hit=memory events=%s elapsed_ms=%.2f",
                len(_polymarket_cache["events"]),
                (time.perf_counter() - started_at) * 1000,
            )
            return deepcopy(_polymarket_cache["events"])

        if not refresh:
            redis_started_at = time.perf_counter()
            cached_events = await WorldCupService._get_cached_json(WorldCupService._polymarket_cache_key)
            logger.info(
                "worldcup.polymarket_cache redis_lookup hit=%s elapsed_ms=%.2f",
                bool(cached_events),
                (time.perf_counter() - redis_started_at) * 1000,
            )
            if cached_events:
                _polymarket_cache["events"] = deepcopy(cached_events)
                _polymarket_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
                logger.info(
                    "worldcup.polymarket_cache hit=redis events=%s elapsed_ms=%.2f",
                    len(cached_events),
                    (time.perf_counter() - started_at) * 1000,
                )
                return cached_events

        try:
            fetch_started_at = time.perf_counter()
            async with httpx.AsyncClient(**WorldCupService._polymarket_client_kwargs()) as client:
                response = await client.get(
                    f"{settings.WORLDCUP_POLYMARKET_API_BASE}/events",
                    params={
                        "closed": "false",
                        "limit": settings.WORLDCUP_POLYMARKET_LIMIT,
                        "tag_slug": "fifa-world-cup",
                    },
                )
                response.raise_for_status()
                logger.info(
                    "worldcup.polymarket_http status=%s content_type=%s url=%s",
                    response.status_code,
                    response.headers.get("content-type"),
                    str(response.request.url),
                )
                payload = response.json()
                if isinstance(payload, list):
                    _polymarket_cache["events"] = deepcopy(payload)
                    _polymarket_cache["expires_at"] = now + timedelta(seconds=settings.WORLDCUP_SCHEDULE_CACHE_SECONDS)
                    logger.info(
                        "worldcup.polymarket_fetch events=%s sample_event_id=%s elapsed_ms=%.2f",
                        len(payload),
                        payload[0].get("id") if payload and isinstance(payload[0], dict) else None,
                        (time.perf_counter() - fetch_started_at) * 1000,
                    )
                    redis_store_started_at = time.perf_counter()
                    await WorldCupService._set_cached_json(
                        WorldCupService._polymarket_cache_key,
                        payload,
                        settings.WORLDCUP_SCHEDULE_CACHE_SECONDS,
                    )
                    logger.info(
                        "worldcup.polymarket_cache store=redis events=%s elapsed_ms=%.2f total_elapsed_ms=%.2f",
                        len(payload),
                        (time.perf_counter() - redis_store_started_at) * 1000,
                        (time.perf_counter() - started_at) * 1000,
                    )
                    return payload
                logger.warning(
                    "worldcup.polymarket_fetch unexpected_payload_type=%s body_preview=%s elapsed_ms=%.2f",
                    type(payload).__name__,
                    str(payload)[:300],
                    (time.perf_counter() - fetch_started_at) * 1000,
                )
        except json.JSONDecodeError as exc:
            logger.warning(
                "worldcup.polymarket_fetch failed=json_decode detail=%s elapsed_ms=%.2f",
                exc,
                (time.perf_counter() - started_at) * 1000,
            )
            return []
        except Exception as exc:
            logger.warning(
                "worldcup.polymarket_fetch failed=%s detail=%s elapsed_ms=%.2f",
                exc.__class__.__name__,
                exc,
                (time.perf_counter() - started_at) * 1000,
            )
            return []
        logger.warning(
            "worldcup.polymarket_fetch empty_result elapsed_ms=%.2f",
            (time.perf_counter() - started_at) * 1000,
        )
        return []

    @staticmethod
    def _polymarket_client_kwargs() -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"timeout": 10.0}
        proxy_url = WorldCupService._polymarket_proxy_url()
        if proxy_url:
            kwargs["proxy"] = proxy_url
            logger.info("worldcup.polymarket_proxy enabled=true proxy=%s", proxy_url)
        else:
            logger.info("worldcup.polymarket_proxy enabled=false")
        return kwargs

    @staticmethod
    def _polymarket_proxy_url() -> str:
        if not settings.WORLDCUP_POLYMARKET_USE_PROXY:
            return ""
        if settings.WORLDCUP_POLYMARKET_PROXY_URL:
            return settings.WORLDCUP_POLYMARKET_PROXY_URL
        if settings.AKSHARE_USE_PROXY and settings.AKSHARE_PROXY_URL:
            return settings.AKSHARE_PROXY_URL
        return ""

    @classmethod
    def _get_redis_url(cls) -> str:
        parsed = urlparse(settings.CELERY_BROKER_URL)
        if parsed.scheme.startswith("redis"):
            return settings.CELERY_BROKER_URL
        return settings.CELERY_RESULT_BACKEND

    @classmethod
    def _get_redis_client(cls) -> redis_asyncio.Redis:
        if cls._redis_client is None:
            cls._redis_client = redis_asyncio.from_url(
                cls._get_redis_url(),
                decode_responses=True,
            )
        return cls._redis_client

    @classmethod
    async def _get_cached_json(cls, key: str) -> Optional[List[Dict[str, Any]]]:
        started_at = time.perf_counter()
        try:
            payload = await cls._get_redis_client().get(key)
            if not payload:
                if key == cls._polymarket_cache_key:
                    logger.info(
                        "worldcup.redis_get key=%s hit=false elapsed_ms=%.2f",
                        key,
                        (time.perf_counter() - started_at) * 1000,
                    )
                return None
            parsed = json.loads(payload)
            if isinstance(parsed, list):
                if key == cls._polymarket_cache_key:
                    logger.info(
                        "worldcup.redis_get key=%s hit=true size=%s elapsed_ms=%.2f",
                        key,
                        len(parsed),
                        (time.perf_counter() - started_at) * 1000,
                    )
                return parsed
            if key == cls._polymarket_cache_key:
                logger.warning(
                    "worldcup.redis_get key=%s unexpected_type=%s elapsed_ms=%.2f",
                    key,
                    type(parsed).__name__,
                    (time.perf_counter() - started_at) * 1000,
                )
        except Exception as exc:
            if key == cls._polymarket_cache_key:
                logger.warning(
                    "worldcup.redis_get key=%s failed=%s elapsed_ms=%.2f",
                    key,
                    exc.__class__.__name__,
                    (time.perf_counter() - started_at) * 1000,
                )
            return None
        return None

    @classmethod
    async def _set_cached_json(cls, key: str, value: List[Dict[str, Any]], ttl_seconds: int) -> None:
        started_at = time.perf_counter()
        try:
            await cls._get_redis_client().set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=ttl_seconds,
            )
            if key == cls._polymarket_cache_key:
                logger.info(
                    "worldcup.redis_set key=%s size=%s ttl=%s elapsed_ms=%.2f",
                    key,
                    len(value),
                    ttl_seconds,
                    (time.perf_counter() - started_at) * 1000,
                )
        except Exception as exc:
            if key == cls._polymarket_cache_key:
                logger.warning(
                    "worldcup.redis_set key=%s failed=%s elapsed_ms=%.2f",
                    key,
                    exc.__class__.__name__,
                    (time.perf_counter() - started_at) * 1000,
                )
            return None

    @classmethod
    async def _get_bankroll_ledger(cls) -> List[Dict[str, Any]]:
        try:
            payload = await cls._get_redis_client().get(cls._bankroll_ledger_key)
            if payload:
                parsed = json.loads(payload)
                if isinstance(parsed, list):
                    _bankroll_ledger_cache["bets"] = deepcopy(parsed)
                    return deepcopy(parsed)
        except Exception:
            pass
        return deepcopy(_bankroll_ledger_cache["bets"])

    @classmethod
    async def _set_bankroll_ledger(cls, ledger: List[Dict[str, Any]]) -> None:
        _bankroll_ledger_cache["bets"] = deepcopy(ledger)
        try:
            await cls._get_redis_client().set(
                cls._bankroll_ledger_key,
                json.dumps(ledger, ensure_ascii=False),
            )
        except Exception:
            return None

    @classmethod
    async def _get_cached_object(cls, key: str) -> Optional[Dict[str, Any]]:
        try:
            payload = await cls._get_redis_client().get(key)
            if not payload:
                return None
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @classmethod
    async def _set_cached_object(cls, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        try:
            await cls._get_redis_client().set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=ttl_seconds,
            )
        except Exception:
            return None

    @classmethod
    async def clear_cached_worldcup_data(cls) -> None:
        _schedule_cache["matches"] = []
        _schedule_cache["expires_at"] = None
        _polymarket_cache["events"] = []
        _polymarket_cache["expires_at"] = None
        _bankroll_ledger_cache["bets"] = []
        _ai_analysis_cache.clear()
        try:
            redis_client = cls._get_redis_client()
            await redis_client.delete(
                cls._schedule_cache_key,
                cls._polymarket_cache_key,
                cls._bankroll_ledger_key,
                cls._matches_index_key,
                cls._match_dates_index_key,
            )
            match_keys = [key async for key in redis_client.scan_iter(match=f"{cls._match_key_prefix}*")]
            if match_keys:
                await redis_client.delete(*match_keys)
            date_keys = [key async for key in redis_client.scan_iter(match=f"{cls._match_date_key_prefix}*")]
            if date_keys:
                await redis_client.delete(*date_keys)
            ai_keys = [key async for key in redis_client.scan_iter(match=f"{cls._ai_analysis_cache_key_prefix}*")]
            if ai_keys:
                await redis_client.delete(*ai_keys)
        except Exception:
            return None

    @staticmethod
    def _map_espn_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        competitions = event.get("competitions") or []
        if not competitions:
            return None

        competition = competitions[0]
        competitors = competition.get("competitors") or []
        home = next((item for item in competitors if item.get("homeAway") == "home"), None)
        away = next((item for item in competitors if item.get("homeAway") == "away"), None)
        if not home or not away:
            return None

        home_team = (home.get("team") or {}).get("displayName") or (home.get("team") or {}).get("name")
        away_team = (away.get("team") or {}).get("displayName") or (away.get("team") or {}).get("name")
        if not home_team or not away_team:
            return None

        stage_name = WorldCupService._extract_stage_name(event, competition)
        stage = STAGE_LABELS.get(stage_name, stage_name)
        group_name = WorldCupService._extract_group_name(competition.get("altGameNote"))
        links = event.get("links") or []
        odds = (competition.get("odds") or [])

        match = {
            "match_id": str(event.get("id")),
            "stage": stage,
            "group_name": group_name,
            "kickoff_at": event.get("date"),
            "home_team": home_team,
            "away_team": away_team,
            "venue": WorldCupService._extract_venue_name(competition, event),
            "status": WorldCupService._map_status((competition.get("status") or {}).get("type") or {}),
            "home_score": WorldCupService._to_int(home.get("score")),
            "away_score": WorldCupService._to_int(away.get("score")),
            "source": "espn_schedule",
            "external_url": WorldCupService._extract_external_url(links),
            "featured_pick": WorldCupService._pending_pick(),
            "key_market": WorldCupService._pending_market(),
            "markets": [],
            "line_movement": [],
            "polymarket_probabilities": {},
        }
        if isinstance(odds, list):
            first_valid_odds = next((item for item in odds if isinstance(item, dict)), None)
            if first_valid_odds:
                WorldCupService._apply_espn_odds(match, first_valid_odds)
        return match

    @staticmethod
    def _build_phase_breakdown(matches: List[Dict[str, Any]], ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        performance: Dict[str, Dict[str, float]] = {}
        for match in matches:
            counts[match["stage"]] = counts.get(match["stage"], 0) + 1
        for bet in ledger:
            if not WorldCupService._is_bet_closed(bet):
                continue
            stage = str(bet.get("stage") or "小组赛")
            bucket = performance.setdefault(stage, {"settled": 0.0, "wins": 0.0, "stake": 0.0, "pnl": 0.0})
            bucket["settled"] += 1
            bucket["stake"] += float(bet.get("stake_amount") or 0.0)
            bucket["pnl"] += float(bet.get("pnl") or 0.0)
            if bet.get("status") == "won":
                bucket["wins"] += 1
        ordered_stages = ["小组赛", "32强", "16强", "8强", "半决赛", "季军赛", "决赛"]
        return [
            {
                "phase": stage,
                "matches": counts.get(stage, 0),
                "roi": round(
                    performance.get(stage, {}).get("pnl", 0.0) / performance.get(stage, {}).get("stake", 1.0) * 100,
                    2,
                )
                if performance.get(stage, {}).get("stake")
                else 0.0,
                "hit_rate": round(
                    performance.get(stage, {}).get("wins", 0.0)
                    / performance.get(stage, {}).get("settled", 1.0)
                    * 100,
                    1,
                )
                if performance.get(stage, {}).get("settled")
                else 0.0,
            }
            for stage in ordered_stages
            if counts.get(stage, 0) or performance.get(stage) or stage in {"小组赛", "32强", "16强"}
        ]

    @staticmethod
    async def _sync_bankroll_ledger(matches: List[Dict[str, Any]]) -> None:
        ledger = await WorldCupService._get_bankroll_ledger()
        ledger_by_match = {str(item.get("match_id")): item for item in ledger}
        changed = False

        for match in sorted(matches, key=WorldCupService._sort_match_by_kickoff):
            existing = ledger_by_match.get(match["match_id"])
            if not existing:
                snapshot = WorldCupService._build_bet_snapshot(
                    match,
                    WorldCupService._build_bankroll_summary(ledger)["bankroll"],
                )
                if snapshot:
                    ledger.append(snapshot)
                    ledger_by_match[match["match_id"]] = snapshot
                    existing = snapshot
                    changed = True
            if existing and WorldCupService._settle_bet_snapshot(existing, match):
                changed = True

        if changed:
            ledger.sort(key=WorldCupService._ledger_sort_key)
            await WorldCupService._set_bankroll_ledger(ledger)

    @staticmethod
    def _build_bet_snapshot(match: Dict[str, Any], bankroll: float) -> Optional[Dict[str, Any]]:
        if not WorldCupService._is_match_ready_to_place(match):
            return None
        featured_pick = match.get("featured_pick") or {}
        bet_type = str(featured_pick.get("bet_type") or "")
        if bet_type not in {"h2h", "asian_handicap", "totals"}:
            return None
        stake_pct = float(featured_pick.get("stake_pct") or 0.0)
        signal_label = str(featured_pick.get("signal_label") or "").strip()
        if stake_pct <= 0 or not signal_label:
            return None
        if featured_pick.get("strategy") in {"待同步", "无优势"}:
            return None
        stake_amount = round(bankroll * stake_pct / 100, 2)
        if stake_amount <= 0:
            return None

        market = WorldCupService._find_market(match, bet_type)
        if not market:
            return None
        option = next((item for item in market.get("options", []) if item.get("label") == signal_label), None)
        if not option:
            return None

        return {
            "match_id": match["match_id"],
            "stage": match["stage"],
            "kickoff_at": match["kickoff_at"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "bet_type": bet_type,
            "side": featured_pick.get("side"),
            "signal_label": signal_label,
            "strategy": featured_pick.get("strategy"),
            "market_line": market.get("line"),
            "odds": float(option.get("odds") or 0.0),
            "stake_pct": stake_pct,
            "stake_amount": round(stake_amount, 2),
            "status": "open",
            "pnl": 0.0,
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "settled_at": None,
            "result_label": None,
        }

    @staticmethod
    def _is_match_ready_to_place(match: Dict[str, Any]) -> bool:
        return WorldCupService._needs_prekick_attention(match, now=datetime.now(timezone.utc))

    @staticmethod
    def _needs_prekick_attention(match: Dict[str, Any], now: datetime) -> bool:
        if match.get("status") in {"live", "settled"}:
            return True
        kickoff_at = str(match.get("kickoff_at") or "")
        if not kickoff_at:
            return False
        try:
            kickoff_dt = datetime.fromisoformat(kickoff_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return kickoff_dt - PREKICK_ENTRY_WINDOW <= now

    @staticmethod
    def _settle_bet_snapshot(bet: Dict[str, Any], match: Dict[str, Any]) -> bool:
        if WorldCupService._is_bet_closed(bet):
            return False
        if match.get("status") != "settled":
            return False
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        if home_score is None or away_score is None:
            return False

        if home_score > away_score:
            result_label = match["home_team"]
        elif away_score > home_score:
            result_label = match["away_team"]
        else:
            result_label = "平局"

        stake_amount = float(bet.get("stake_amount") or 0.0)
        odds = float(bet.get("odds") or 0.0)
        settlement = WorldCupService._settle_bet_outcome(
            bet=bet,
            match=match,
            home_score=home_score,
            away_score=away_score,
            result_label=result_label,
            stake_amount=stake_amount,
            odds=odds,
        )
        if not settlement:
            return False

        bet["status"] = settlement["status"]
        bet["pnl"] = settlement["pnl"]
        bet["result_label"] = result_label
        bet["settled_at"] = datetime.now(timezone.utc).isoformat()
        return True

    @staticmethod
    def _settle_bet_outcome(
        bet: Dict[str, Any],
        match: Dict[str, Any],
        home_score: int,
        away_score: int,
        result_label: str,
        stake_amount: float,
        odds: float,
    ) -> Optional[Dict[str, Any]]:
        bet_type = str(bet.get("bet_type") or "")
        signal_label = str(bet.get("signal_label") or "")

        if bet_type == "h2h":
            is_win = signal_label == result_label
            return {
                "status": "won" if is_win else "lost",
                "pnl": round(stake_amount * (odds - 1), 2) if is_win else round(-stake_amount, 2),
            }

        if bet_type == "asian_handicap":
            handicap = WorldCupService._extract_line_from_label(signal_label)
            if handicap is None:
                handicap = WorldCupService._to_float(bet.get("market_line"))
            if handicap is None:
                return None
            if signal_label.startswith(match["home_team"]):
                base_score = home_score
                opponent_score = away_score
            elif signal_label.startswith(match["away_team"]):
                base_score = away_score
                opponent_score = home_score
            else:
                return None
            return WorldCupService._settle_split_line_bet(
                stake_amount=stake_amount,
                odds=odds,
                lines=WorldCupService._split_asian_line(handicap),
                evaluator=lambda line: WorldCupService._grade_margin(base_score + line - opponent_score),
            )

        if bet_type == "totals":
            total_line = WorldCupService._extract_line_from_label(signal_label)
            if total_line is None:
                total_line = WorldCupService._to_float(bet.get("market_line"))
            if total_line is None:
                return None
            total_goals = home_score + away_score
            if signal_label.startswith("大"):
                return WorldCupService._settle_split_line_bet(
                    stake_amount=stake_amount,
                    odds=odds,
                    lines=WorldCupService._split_asian_line(total_line),
                    evaluator=lambda line: WorldCupService._grade_margin(total_goals - line),
                )
            if signal_label.startswith("小"):
                return WorldCupService._settle_split_line_bet(
                    stake_amount=stake_amount,
                    odds=odds,
                    lines=WorldCupService._split_asian_line(total_line),
                    evaluator=lambda line: WorldCupService._grade_margin(line - total_goals),
                )
            return None

        return None

    @staticmethod
    def _settle_split_line_bet(
        stake_amount: float,
        odds: float,
        lines: List[float],
        evaluator: Any,
    ) -> Dict[str, Any]:
        if not lines:
            return {"status": "void", "pnl": 0.0}
        stake_per_leg = stake_amount / len(lines)
        pnl = 0.0
        results: List[str] = []
        for line in lines:
            grade = evaluator(line)
            results.append(grade)
            if grade == "win":
                pnl += stake_per_leg * (odds - 1)
            elif grade == "loss":
                pnl -= stake_per_leg

        rounded_pnl = round(pnl, 2)
        if all(item == "push" for item in results):
            status = "push"
        elif rounded_pnl > 0:
            status = "won"
        elif rounded_pnl < 0:
            status = "lost"
        else:
            status = "push"
        return {"status": status, "pnl": rounded_pnl}

    @staticmethod
    def _split_asian_line(line: float) -> List[float]:
        scaled = int(round(line * 100))
        remainder = abs(scaled) % 100
        if remainder in {25, 75}:
            return [round(line - 0.25, 2), round(line + 0.25, 2)]
        return [round(line, 2)]

    @staticmethod
    def _grade_margin(margin: float) -> str:
        if margin > 0:
            return "win"
        if margin < 0:
            return "loss"
        return "push"

    @staticmethod
    def _extract_line_from_label(label: str) -> Optional[float]:
        matched = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", label.strip())
        if not matched:
            return None
        return WorldCupService._to_float(matched.group(1))

    @staticmethod
    def _build_bankroll_summary(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
        settled_bets = [bet for bet in ledger if WorldCupService._is_bet_closed(bet)]
        open_bets = [bet for bet in ledger if bet.get("status") == "open"]
        settled_bets.sort(key=WorldCupService._ledger_sort_key)

        bankroll = INITIAL_BANKROLL
        peak = INITIAL_BANKROLL
        max_drawdown = 0.0
        bankroll_curve = [{"label": "初始", "bankroll": INITIAL_BANKROLL, "pnl": 0.0}]

        for bet in settled_bets:
            bankroll = round(bankroll + float(bet.get("pnl") or 0.0), 2)
            peak = max(peak, bankroll)
            if peak > 0:
                max_drawdown = min(max_drawdown, (bankroll - peak) / peak * 100)
            bankroll_curve.append(
                {
                    "label": WorldCupService._curve_label(bet),
                    "bankroll": bankroll,
                    "pnl": round(bankroll - INITIAL_BANKROLL, 2),
                }
            )

        if len(bankroll_curve) == 1:
            bankroll_curve.append({"label": "当前", "bankroll": INITIAL_BANKROLL, "pnl": 0.0})

        realized_pnl = round(bankroll - INITIAL_BANKROLL, 2)
        return {
            "bankroll": bankroll,
            "roi": round(realized_pnl / INITIAL_BANKROLL * 100, 2),
            "max_drawdown": round(max_drawdown, 2),
            "settled_matches": len(settled_bets),
            "open_positions": len(open_bets),
            "bankroll_curve": bankroll_curve,
        }

    @staticmethod
    def _curve_label(bet: Dict[str, Any]) -> str:
        kickoff_at = str(bet.get("kickoff_at") or "")
        try:
            dt = datetime.fromisoformat(kickoff_at.replace("Z", "+00:00"))
            prefix = dt.strftime("%m-%d")
        except ValueError:
            prefix = "结算"
        return f'{prefix} {bet.get("home_team", "")} vs {bet.get("away_team", "")}'.strip()

    @staticmethod
    def _ledger_sort_key(bet: Dict[str, Any]) -> tuple[str, str]:
        return (str(bet.get("kickoff_at") or ""), str(bet.get("match_id") or ""))

    @staticmethod
    def _is_bet_closed(bet: Dict[str, Any]) -> bool:
        return str(bet.get("status") or "") in {"won", "lost", "push", "void"}

    @staticmethod
    def _serialize_bankroll_bet(bet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not bet:
            return None
        return {
            "bet_type": bet.get("bet_type"),
            "side": bet.get("side"),
            "signal_label": bet.get("signal_label"),
            "strategy": bet.get("strategy"),
            "odds": bet.get("odds"),
            "stake_pct": bet.get("stake_pct"),
            "stake_amount": bet.get("stake_amount"),
            "status": bet.get("status"),
            "pnl": bet.get("pnl"),
            "placed_at": bet.get("placed_at"),
            "settled_at": bet.get("settled_at"),
            "result_label": bet.get("result_label"),
        }

    @staticmethod
    async def _get_ai_analysis(match: Dict[str, Any], refresh: bool = False) -> Dict[str, Any]:
        cache_key = f'{WorldCupService._ai_analysis_cache_key_prefix}{match["match_id"]}'
        if not refresh and match["match_id"] in _ai_analysis_cache:
            return deepcopy(_ai_analysis_cache[match["match_id"]])
        if not refresh:
            cached = await WorldCupService._get_cached_object(cache_key)
            if cached:
                _ai_analysis_cache[match["match_id"]] = deepcopy(cached)
                return cached

        analysis = await WorldCupService._generate_ai_analysis(match)
        _ai_analysis_cache[match["match_id"]] = deepcopy(analysis)
        await WorldCupService._set_cached_object(cache_key, analysis, 6 * 60 * 60)
        return analysis

    @staticmethod
    async def _generate_ai_analysis(match: Dict[str, Any]) -> Dict[str, Any]:
        client = LLMRegistry.get_client(LLMProfileName.RESEARCH)
        if not client.api_key:
            raise RuntimeError("未配置 AI 分析模型或 API Key")
        prompt = WorldCupService._worldcup_ai_prompt(match)
        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是专业足球盘口分析师。你只能基于用户提供的结构化市场数据进行解释，"
                            "不能杜撰伤停、新闻或历史事实。输出必须是 JSON。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=700,
            )
        except Exception as exc:
            raise RuntimeError(f"AI 分析请求失败: {exc}") from exc

        content = (response.get("choices", [{}])[0].get("message", {}) or {}).get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        parsed = WorldCupService._parse_ai_analysis_content(content or "")
        if not parsed:
            raise RuntimeError("AI 分析返回内容无法解析为有效 JSON")
        parsed["source"] = "llm"
        parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
        return parsed

    @staticmethod
    def _parse_ai_analysis_content(content: str) -> Optional[Dict[str, Any]]:
        text = content.strip()
        if text.startswith("```"):
            matched = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if matched:
                text = matched.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        risk_flags = parsed.get("risk_flags")
        if not isinstance(risk_flags, list):
            risk_flags = []
        return {
            "summary": str(parsed.get("summary") or "").strip() or None,
            "bull_case": str(parsed.get("bull_case") or "").strip() or None,
            "bear_case": str(parsed.get("bear_case") or "").strip() or None,
            "market_note": str(parsed.get("market_note") or "").strip() or None,
            "confidence_note": str(parsed.get("confidence_note") or "").strip() or None,
            "risk_flags": [str(item) for item in risk_flags if str(item).strip()],
        }

    @staticmethod
    def _worldcup_ai_prompt(match: Dict[str, Any]) -> str:
        featured_pick = match.get("featured_pick") or {}
        markets = []
        for market in match.get("markets", []):
            markets.append(
                {
                    "market_type": market.get("market_type"),
                    "title": market.get("title"),
                    "line": market.get("line"),
                    "options": market.get("options"),
                }
            )
        payload = {
            "match": {
                "home_team": match.get("home_team"),
                "away_team": match.get("away_team"),
                "stage": match.get("stage"),
                "status": match.get("status"),
                "kickoff_at": match.get("kickoff_at"),
            },
            "featured_pick": featured_pick,
            "polymarket_probabilities": match.get("polymarket_probabilities"),
            "markets": markets,
            "bankroll_bet": match.get("bankroll_bet"),
        }
        return (
            "请基于以下世界杯比赛结构化数据，输出一个 JSON 对象，字段必须包含："
            "summary, bull_case, bear_case, market_note, confidence_note, risk_flags。"
            "risk_flags 必须是字符串数组。不要输出 markdown。\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _extract_stage_name(event: Dict[str, Any], competition: Dict[str, Any]) -> str:
        season = event.get("season") or {}
        if isinstance(season, dict):
            season_type = season.get("type")
            if isinstance(season_type, dict):
                name = season_type.get("name")
                if isinstance(name, str) and name:
                    return name

        note = competition.get("altGameNote")
        if isinstance(note, str):
            if "Group" in note:
                return "Group Stage"
            if "Round of 32" in note:
                return "Round of 32"
            if "Round of 16" in note:
                return "Round of 16"
            if "Quarterfinal" in note:
                return "Quarterfinals"
            if "Semifinal" in note:
                return "Semifinals"
            if "3rd-Place" in note or "Third-Place" in note:
                return "3rd-Place Match"
            if note.strip().endswith("Final"):
                return "Final"

        return "Group Stage"

    @staticmethod
    def _extract_group_name(note: Optional[str]) -> Optional[str]:
        if not note:
            return None
        matched = re.search(r"Group\s+([A-L])", note, re.IGNORECASE)
        if matched:
            return f"{matched.group(1).upper()}组"
        return None

    @staticmethod
    def _map_status(status_type: Dict[str, Any]) -> str:
        state = status_type.get("state")
        if state == "post":
            return "settled"
        if state == "in":
            return "live"
        return "upcoming"

    @staticmethod
    def _pending_pick() -> Dict[str, Any]:
        return {
            "bet_type": "h2h",
            "strategy": "待同步",
            "side": "等待赔率同步",
            "signal_label": None,
            "book_probability": None,
            "fair_probability": None,
            "confidence": 0,
            "edge": 0.0,
            "stake_pct": 0.0,
            "stake_amount": 0.0,
            "rationale": [
                "已接入真实世界杯赛程。",
                "当前比赛的赔率/预测市场尚未完成同步。",
                "接入更多盘口后再生成正式推荐。",
            ],
        }

    @staticmethod
    def _pending_market() -> Dict[str, Any]:
        return {
            "market_type": "polymarket",
            "title": "待同步市场",
            "line": None,
            "options": [],
        }

    @staticmethod
    def _match_polymarket_event(match: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        home_aliases = WorldCupService._team_aliases(match["home_team"])
        away_aliases = WorldCupService._team_aliases(match["away_team"])

        for event in events:
            teams = event.get("teams")
            if isinstance(teams, list):
                event_team_names = [
                    WorldCupService._normalize_text(str(team.get("name", "")))
                    for team in teams
                    if isinstance(team, dict) and team.get("name")
                ]
                if any(alias == team_name for alias in home_aliases for team_name in event_team_names) and any(
                    alias == team_name for alias in away_aliases for team_name in event_team_names
                ):
                    return event
            haystack = WorldCupService._normalize_text(
                " ".join(str(event.get(field, "")) for field in ("title", "slug", "description", "ticker"))
            )
            if any(alias in haystack for alias in home_aliases) and any(alias in haystack for alias in away_aliases):
                return event
        return None

    @staticmethod
    def _team_aliases(team_name: str) -> List[str]:
        base = WorldCupService._normalize_text(team_name)
        aliases = [base]
        aliases.extend(WorldCupService._normalize_text(item) for item in TEAM_ALIASES.get(team_name, []))
        return [alias for alias in aliases if alias]

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _extract_market_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        markets = event.get("markets")
        if not isinstance(markets, list) or not markets:
            return None

        sports_market = WorldCupService._extract_soccer_event_market(event, markets)
        if sports_market:
            return sports_market

        market = markets[0]
        outcomes = WorldCupService._json_list(market.get("outcomes"))
        prices = WorldCupService._json_list(market.get("outcomePrices"))
        if not outcomes or not prices:
            return None

        options = []
        for label, raw_prob in zip(outcomes[:3], prices[:3]):
            try:
                probability = float(raw_prob)
            except (TypeError, ValueError):
                continue
            if probability <= 0:
                continue
            options.append(
                {
                    "label": str(label),
                    "odds": round(1 / probability, 2),
                    "probability": probability,
                }
            )

        if not options:
            return None

        return {
            "market_type": "polymarket",
            "title": event.get("title") or market.get("question") or "Polymarket",
            "line": None,
            "options": options,
        }

    @staticmethod
    def _extract_soccer_event_market(event: Dict[str, Any], markets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        teams = event.get("teams")
        if not isinstance(teams, list) or len(teams) < 2:
            return None

        home_team = next(
            (
                str(team.get("name"))
                for team in teams
                if isinstance(team, dict) and str(team.get("ordering", "")).lower() == "home" and team.get("name")
            ),
            None,
        )
        away_team = next(
            (
                str(team.get("name"))
                for team in teams
                if isinstance(team, dict) and str(team.get("ordering", "")).lower() == "away" and team.get("name")
            ),
            None,
        )
        if not home_team or not away_team:
            return None

        raw_probabilities: Dict[str, float] = {}
        home_aliases = WorldCupService._team_aliases(home_team)
        away_aliases = WorldCupService._team_aliases(away_team)

        for market in markets:
            if not isinstance(market, dict):
                continue
            probability = WorldCupService._extract_binary_yes_probability(market)
            if probability is None:
                continue

            text = WorldCupService._normalize_text(
                " ".join(
                    str(market.get(field, ""))
                    for field in ("question", "groupItemTitle", "slug", "description")
                )
            )
            if any(alias in text for alias in home_aliases):
                raw_probabilities[home_team] = probability
                continue
            if any(alias in text for alias in away_aliases):
                raw_probabilities[away_team] = probability
                continue
            if "draw" in text or "tie" in text:
                raw_probabilities["平局"] = probability

        if len(raw_probabilities) < 2:
            return None

        total_probability = sum(raw_probabilities.values())
        if total_probability <= 0:
            return None

        options = []
        for label, probability in raw_probabilities.items():
            normalized_probability = probability / total_probability
            if normalized_probability <= 0:
                continue
            options.append(
                {
                    "label": label,
                    "odds": round(1 / normalized_probability, 2),
                    "probability": round(normalized_probability, 4),
                }
            )

        if not options:
            return None

        preferred_order = {home_team: 0, "平局": 1, away_team: 2}
        options.sort(key=lambda item: preferred_order.get(item["label"], 9))
        return {
            "market_type": "polymarket",
            "title": event.get("title") or "Polymarket",
            "line": None,
            "options": options,
        }

    @staticmethod
    def _extract_binary_yes_probability(market: Dict[str, Any]) -> Optional[float]:
        prices = WorldCupService._json_list(market.get("outcomePrices"))
        if prices:
            try:
                probability = float(prices[0])
            except (TypeError, ValueError):
                probability = None
            if probability is not None and probability > 0:
                return probability

        for field in ("lastTradePrice", "bestBid", "bestAsk"):
            try:
                probability = float(market.get(field))
            except (TypeError, ValueError):
                continue
            if probability > 0:
                return probability
        return None

    @staticmethod
    def _json_list(value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    def _apply_polymarket_event(match: Dict[str, Any], event: Dict[str, Any]) -> None:
        market = WorldCupService._extract_market_from_event(event)
        if not market:
            return

        match["source"] = "polymarket_live"
        slug = event.get("slug")
        if slug:
            match["external_url"] = f"https://polymarket.com/event/{slug}"
        match["key_market"] = deepcopy(market)
        match["markets"] = [item for item in match["markets"] if item.get("market_type") != "polymarket"]
        match["markets"].append(deepcopy(market))
        match["polymarket_probabilities"] = {
            option["label"]: option["probability"] for option in market["options"]
        }
        WorldCupService._refresh_featured_pick(match)

    @staticmethod
    def _apply_espn_odds(match: Dict[str, Any], odds: Dict[str, Any]) -> None:
        if not isinstance(odds, dict):
            return

        markets: List[Dict[str, Any]] = []

        h2h_market = WorldCupService._build_h2h_market(match, odds)
        if h2h_market:
            markets.append(h2h_market)

        spread_market = WorldCupService._build_spread_market(match, odds)
        if spread_market:
            markets.append(spread_market)

        totals_market = WorldCupService._build_totals_market(odds)
        if totals_market:
            markets.append(totals_market)

        if not markets:
            return

        match["markets"] = markets
        match["key_market"] = deepcopy(h2h_market or spread_market or totals_market)
        match["featured_pick"] = {
            "bet_type": "h2h" if h2h_market else "asian_handicap" if spread_market else "totals",
            "side": "待模型生成",
            "confidence": 0,
            "edge": 0.0,
            "stake_pct": 0.0,
            "stake_amount": 0.0,
            "rationale": [
                "真实赛程与 DraftKings 赔率已同步。",
                "当前页面先展示市场原始定价，不直接生成投注建议。",
                "下一步可在此基础上接入让球/大小球预测模型。",
            ],
        }
        line_movement = WorldCupService._build_line_movement(odds)
        if line_movement:
            match["line_movement"] = line_movement
        WorldCupService._refresh_featured_pick(match)

    @staticmethod
    def _refresh_featured_pick(match: Dict[str, Any]) -> None:
        h2h_market = WorldCupService._find_market(match, "h2h")
        spread_market = WorldCupService._find_market(match, "asian_handicap")
        totals_market = WorldCupService._find_market(match, "totals")

        candidates: List[Dict[str, Any]] = []
        candidates.extend(WorldCupService._polymarket_value_candidates(match, h2h_market))
        fallback_candidate = WorldCupService._market_consensus_candidate(match, spread_market, totals_market, h2h_market)
        if fallback_candidate:
            candidates.append(fallback_candidate)

        if not candidates:
            match["featured_pick"] = WorldCupService._pending_pick()
            if h2h_market or spread_market or totals_market:
                match["featured_pick"]["side"] = "观望"
                match["featured_pick"]["strategy"] = "无优势"
                match["featured_pick"]["signal_label"] = None
                match["featured_pick"]["book_probability"] = None
                match["featured_pick"]["fair_probability"] = None
                match["featured_pick"]["rationale"] = [
                    "真实赔率已同步，但当前没有形成足够清晰的价差优势。",
                    "建议等待 Polymarket 概率、盘口移动或更多市场共振后再出手。",
                    "当前页面优先展示市场定价，不强行给出高风险推荐。",
                ]
            return

        best = max(candidates, key=lambda item: item["edge"])
        stake_pct = WorldCupService._stake_pct_from_edge(best["edge"])
        confidence = WorldCupService._confidence_from_edge(best["edge"], best.get("strength", 0.0))
        match["featured_pick"] = {
            "bet_type": best["bet_type"],
            "strategy": best["strategy"],
            "side": best["side"],
            "signal_label": best.get("signal_label"),
            "book_probability": best.get("book_probability"),
            "fair_probability": best.get("fair_probability"),
            "confidence": confidence,
            "edge": round(best["edge"] * 100, 2),
            "stake_pct": stake_pct,
            "stake_amount": round(INITIAL_BANKROLL * stake_pct / 100, 2),
            "rationale": best["rationale"],
        }
        if best.get("market_type"):
            market = WorldCupService._find_market(match, best["market_type"])
            if market:
                match["key_market"] = deepcopy(market)

    @staticmethod
    def _find_market(match: Dict[str, Any], market_type: str) -> Optional[Dict[str, Any]]:
        return next((item for item in match.get("markets", []) if item.get("market_type") == market_type), None)

    @staticmethod
    def _polymarket_value_candidates(match: Dict[str, Any], h2h_market: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not h2h_market or not match.get("polymarket_probabilities"):
            return []

        bookmaker_probs = {option["label"]: option["probability"] for option in h2h_market.get("options", [])}
        polymarket_map = WorldCupService._normalize_probability_labels(match)
        candidates = []

        label_map = {
            match["home_team"]: polymarket_map.get("home"),
            "平局": polymarket_map.get("draw"),
            match["away_team"]: polymarket_map.get("away"),
        }
        for label, book_prob in bookmaker_probs.items():
            poly_prob = label_map.get(label)
            if poly_prob is None:
                continue
            edge = poly_prob - book_prob
            if edge < 0.03:
                continue
            candidates.append(
                {
                    "bet_type": "h2h",
                    "strategy": "价值单",
                    "market_type": "h2h",
                    "side": f"{label} 胜" if label != "平局" else "平局",
                    "signal_label": label,
                    "book_probability": round(book_prob, 4),
                    "fair_probability": round(poly_prob, 4),
                    "edge": edge,
                    "strength": poly_prob,
                    "rationale": [
                        f"Polymarket 对 {label} 的定价高于 ESPN/DraftKings 去水后概率 {edge * 100:.1f} 个百分点。",
                        "同一场比赛同时存在传统赔率与预测市场时，优先抓两者之间的显著价差。",
                        "这类信号更适合做小仓位价值单，而不是重仓方向单。",
                    ],
                }
            )
        return candidates

    @staticmethod
    def _market_consensus_candidate(
        match: Dict[str, Any],
        spread_market: Optional[Dict[str, Any]],
        totals_market: Optional[Dict[str, Any]],
        h2h_market: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        if spread_market and spread_market.get("options"):
            favorite = max(spread_market["options"], key=lambda item: item["probability"])
            spread_line = WorldCupService._to_float(spread_market.get("line"))
            if favorite["probability"] >= 0.535 and spread_line is not None and abs(spread_line) >= 0.5:
                candidates.append(
                    {
                        "bet_type": "asian_handicap",
                        "strategy": "一致性单",
                        "market_type": "asian_handicap",
                        "side": favorite["label"],
                        "signal_label": favorite["label"],
                        "book_probability": round(favorite["probability"], 4),
                        "fair_probability": None,
                        "edge": max(favorite["probability"] - 0.5, 0.0),
                        "strength": favorite["probability"],
                        "rationale": [
                            "让球盘已经给出明确让步，且优势方在即时赔率下仍保持更高的去水后概率。",
                            "当让球深度与赔率方向一致时，说明市场对强弱判断比较统一。",
                            "这类信号适合作为没有跨市场价差时的基础方向参考。",
                        ],
                    }
                )

        if totals_market and totals_market.get("options"):
            strongest_total = max(totals_market["options"], key=lambda item: item["probability"])
            if strongest_total["probability"] >= 0.545:
                candidates.append(
                    {
                        "bet_type": "totals",
                        "strategy": "一致性单",
                        "market_type": "totals",
                        "side": strongest_total["label"],
                        "signal_label": strongest_total["label"],
                        "book_probability": round(strongest_total["probability"], 4),
                        "fair_probability": None,
                        "edge": max(strongest_total["probability"] - 0.5, 0.0),
                        "strength": strongest_total["probability"],
                        "rationale": [
                            "大小球一侧的去水后概率已经明显高于均衡位。",
                            "在没有跨市场对照时，大小球通常比胜平负更容易形成清晰的一致预期。",
                            "当前逻辑优先选择概率优势更集中的盘口，而不是勉强做胜平负。",
                        ],
                    }
                )

        if not candidates and h2h_market and h2h_market.get("options"):
            leader = max(h2h_market["options"], key=lambda item: item["probability"])
            if leader["probability"] >= 0.5:
                candidates.append(
                    {
                        "bet_type": "h2h",
                        "strategy": "市场共识",
                        "market_type": "h2h",
                        "side": f'{leader["label"]} 胜' if leader["label"] != "平局" else "平局",
                        "signal_label": leader["label"],
                        "book_probability": round(leader["probability"], 4),
                        "fair_probability": None,
                        "edge": max(leader["probability"] - 0.45, 0.0) / 2,
                        "strength": leader["probability"],
                        "rationale": [
                            "当前没有更强的跨市场价差信号，回退为最基础的胜平负市场共识。",
                            "这一类推荐置信度会明显低于 Polymarket 与传统赔率出现分歧时的价值单。",
                            "如果后续盘口继续走深，优先升级为让球或大小球方向。",
                        ],
                    }
                )

        return max(candidates, key=lambda item: item["edge"]) if candidates else None

    @staticmethod
    def _normalize_probability_labels(match: Dict[str, Any]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        home_aliases = WorldCupService._team_aliases(match["home_team"])
        away_aliases = WorldCupService._team_aliases(match["away_team"])

        for raw_label, probability in (match.get("polymarket_probabilities") or {}).items():
            label = WorldCupService._normalize_text(raw_label)
            raw_lower = str(raw_label).lower()
            if any(alias in label for alias in home_aliases):
                normalized["home"] = probability
            elif any(alias in label for alias in away_aliases):
                normalized["away"] = probability
            elif any(token in label for token in ("draw", "tie")) or "平" in raw_lower:
                normalized["draw"] = probability
        return normalized

    @staticmethod
    def _stake_pct_from_edge(edge: float) -> float:
        if edge >= 0.08:
            return 1.0
        if edge >= 0.05:
            return 0.75
        if edge >= 0.03:
            return 0.5
        return 0.25

    @staticmethod
    def _confidence_from_edge(edge: float, strength: float) -> int:
        score = 45 + edge * 500 + max(strength - 0.5, 0) * 60
        return max(52, min(82, int(round(score))))

    @staticmethod
    def _build_h2h_market(match: Dict[str, Any], odds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        moneyline = odds.get("moneyline") or {}
        home_close = ((moneyline.get("home") or {}).get("close") or {}).get("odds")
        draw_close = ((moneyline.get("draw") or {}).get("close") or {}).get("odds")
        away_close = ((moneyline.get("away") or {}).get("close") or {}).get("odds")

        items = [
            (match["home_team"], home_close),
            ("平局", draw_close),
            (match["away_team"], away_close),
        ]
        options = WorldCupService._market_options_from_american(items)
        if not options:
            return None
        return {"market_type": "h2h", "title": "胜平负", "line": None, "options": options}

    @staticmethod
    def _build_spread_market(match: Dict[str, Any], odds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        spread = odds.get("pointSpread") or {}
        home_close = (spread.get("home") or {}).get("close") or {}
        away_close = (spread.get("away") or {}).get("close") or {}
        line = home_close.get("line")

        items = [
            (f'{match["home_team"]} {home_close.get("line", "")}'.strip(), home_close.get("odds")),
            (f'{match["away_team"]} {away_close.get("line", "")}'.strip(), away_close.get("odds")),
        ]
        options = WorldCupService._market_options_from_american(items)
        if len(options) < 2:
            return None
        return {
            "market_type": "asian_handicap",
            "title": "让球",
            "line": str(line) if line is not None else None,
            "options": options,
        }

    @staticmethod
    def _build_totals_market(odds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        total = odds.get("total") or {}
        over_close = (total.get("over") or {}).get("close") or {}
        under_close = (total.get("under") or {}).get("close") or {}
        over_line = WorldCupService._extract_total_line(over_close.get("line"))
        under_line = WorldCupService._extract_total_line(under_close.get("line"))
        line = over_line or under_line or odds.get("overUnder")

        items = [
            (f"大 {over_line or line}", over_close.get("odds")),
            (f"小 {under_line or line}", under_close.get("odds")),
        ]
        options = WorldCupService._market_options_from_american(items)
        if len(options) < 2:
            return None
        return {
            "market_type": "totals",
            "title": "大小球",
            "line": str(line) if line is not None else None,
            "options": options,
        }

    @staticmethod
    def _build_line_movement(odds: Dict[str, Any]) -> List[Dict[str, Any]]:
        spread = odds.get("pointSpread") or {}
        home = spread.get("home") or {}
        away = spread.get("away") or {}
        open_home = home.get("open") or {}
        open_away = away.get("open") or {}
        close_home = home.get("close") or {}
        close_away = away.get("close") or {}

        points = []
        if open_home or open_away:
            points.append(
                {
                    "label": "开盘",
                    "line": WorldCupService._to_float(open_home.get("line")) or 0.0,
                    "home_odds": WorldCupService._american_to_decimal(open_home.get("odds")) or 0.0,
                    "away_odds": WorldCupService._american_to_decimal(open_away.get("odds")) or 0.0,
                }
            )
        if close_home or close_away:
            points.append(
                {
                    "label": "即时",
                    "line": WorldCupService._to_float(close_home.get("line")) or 0.0,
                    "home_odds": WorldCupService._american_to_decimal(close_home.get("odds")) or 0.0,
                    "away_odds": WorldCupService._american_to_decimal(close_away.get("odds")) or 0.0,
                }
            )
        return points

    @staticmethod
    def _market_options_from_american(items: List[tuple[str, Any]]) -> List[Dict[str, Any]]:
        prepared = []
        for label, raw_odds in items:
            decimal_odds = WorldCupService._american_to_decimal(raw_odds)
            implied_probability = WorldCupService._american_to_implied(raw_odds)
            if decimal_odds is None or implied_probability is None:
                continue
            prepared.append((label, decimal_odds, implied_probability))

        probability_sum = sum(item[2] for item in prepared)
        if not prepared or probability_sum <= 0:
            return []

        return [
            {
                "label": label,
                "odds": decimal_odds,
                "probability": round(implied_probability / probability_sum, 4),
            }
            for label, decimal_odds, implied_probability in prepared
        ]

    @staticmethod
    def _american_to_decimal(value: Any) -> Optional[float]:
        american = WorldCupService._parse_american_odds(value)
        if american is None:
            return None
        if american > 0:
            return round(1 + american / 100, 2)
        return round(1 + 100 / abs(american), 2)

    @staticmethod
    def _american_to_implied(value: Any) -> Optional[float]:
        american = WorldCupService._parse_american_odds(value)
        if american is None:
            return None
        if american > 0:
            return 100 / (american + 100)
        return abs(american) / (abs(american) + 100)

    @staticmethod
    def _parse_american_odds(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            try:
                return int(normalized)
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_total_line(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        return value[1:] if value[:1].lower() in {"o", "u"} else value

    @staticmethod
    def _extract_external_url(links: List[Dict[str, Any]]) -> Optional[str]:
        for link in links:
            href = link.get("href")
            if isinstance(href, str) and href:
                return href
        return None

    @staticmethod
    def _extract_venue_name(competition: Dict[str, Any], event: Dict[str, Any]) -> str:
        competition_venue = competition.get("venue") or {}
        if isinstance(competition_venue, dict):
            full_name = competition_venue.get("fullName")
            if isinstance(full_name, str) and full_name:
                return full_name

        event_venue = event.get("venue") or {}
        if isinstance(event_venue, dict):
            display_name = event_venue.get("displayName")
            if isinstance(display_name, str) and display_name:
                return display_name

        return "待定场地"

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sort_key(match: Dict[str, Any]) -> tuple[int, str]:
        status_rank = {"live": 0, "upcoming": 1, "settled": 2}
        return (status_rank.get(match["status"], 9), match["kickoff_at"])

    @staticmethod
    def _sort_match_by_kickoff(match: Dict[str, Any]) -> tuple[str, str]:
        return (str(match.get("kickoff_at") or ""), str(match.get("match_id") or ""))

    @staticmethod
    def _summary(match: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "match_id": match["match_id"],
            "stage": match["stage"],
            "group_name": match.get("group_name"),
            "kickoff_at": match["kickoff_at"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "venue": match["venue"],
            "status": match["status"],
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "source": match.get("source"),
            "external_url": match.get("external_url"),
            "featured_pick": deepcopy(match["featured_pick"]),
            "key_market": deepcopy(match["key_market"]),
        }
