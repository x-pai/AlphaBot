export type MarketCardLabel = '趋势' | '情绪' | '主线' | '赚钱效应';

export type MarketCardData = {
  facts: string[];
};

export type MarketGeeseStock = {
  name: string;
  code: string;
  change: string;
  note: string;
  result: 'success' | 'failed' | 'broken';
  plate?: string;
};

export type MarketGeeseRow = {
  progress: string;
  numerator: number;
  denominator: number;
  stocks: MarketGeeseStock[];
};

export type MarketBoardStock = {
  name: string;
  code: string;
};

export type MarketBoardLevel = {
  height: number;
  number: number;
  stocks: string[];
  code_list: MarketBoardStock[];
};

export type MarketEmotionPoint = {
  label: string;
  fullDate: string;
  maxHeight: number;
  secondHeight: number;
  maxCount: number;
  secondCount: number;
  maxNames: string[];
  secondNames: string[];
  allLevels: MarketBoardLevel[];
  geeseRows: MarketGeeseRow[];
};

export type MarketPayoffItem = {
  name: string;
  value: string;
  note: string;
  tone?: 'up' | 'down' | 'normal';
};

export type MarketMainlineStock = {
  name: string;
  code: string;
  lbc: number;
};

export type MarketMainlineLane = {
  name: string;
  value: string;
  change: number;
  netFlow: number;
  ztCount: number;
  maxHeight: number;
  upCount: number;
  downCount: number;
  leader: MarketMainlineStock | null;
  followers: MarketMainlineStock[];
  /** 主线综合得分（多维打分，仅用于排序与调试展示） */
  score?: number;
  /** 近 5 个交易日（不含当日）题材上榜天数 */
  persistDays?: number;
  /** xgb 趋势推荐的一句催化描述 */
  catalyst?: string;
};

export type TurnoverMinutePoint = {
  time: string;
  today: number | null;
  yesterday: number | null;
};

export type IntradayEmotionPoint = {
  time: string;
  positive: number | null;
  negative: number | null;
  index: number | null;
};

export type IntradayEmotionSnapshot = {
  positiveCurrent: number | null;
  negativeCurrent: number | null;
  indexCurrent: number | null;
  points: IntradayEmotionPoint[];
};

export type ShortEmotionMinutePoint = {
  time: string;
  value: number;
  turnover: number | null;
};

export type ShortEmotionDay = {
  date: string;
  points: ShortEmotionMinutePoint[];
};

export type ShortEmotionSnapshot = {
  latestValue: number | null;
  latestTurnover: number | null;
  zone: string;
  days: ShortEmotionDay[];
};

export type TurnoverSnapshot = {
  current: number | null;
  predict: number | null;
  previous: number | null;
  change: number | null;
  currentText: string;
  predictText: string;
  previousText: string;
  changeText: string;
  points: TurnoverMinutePoint[];
  emotion: IntradayEmotionSnapshot | null;
};

export type MarketTrendStage = '主升' | '发酵' | '分歧' | '震荡' | '退潮' | '冷却';

export type MarketTrendFlow = 'in' | 'out';

export type MarketTrendHighlightStock = {
  code: string;
  name: string;
  lbc: number;
};

export type MarketTrendTopic = {
  id: string;
  name: string;
  color: string;
  flow: MarketTrendFlow;
  date: string;
  score: number;
  changePct: number;
  moneyFlow: number;
  breadth: number;
  /** 池内涨停家数（涨停池/异动与板块交叉计数） */
  ztCount: number;
  ztRatio: number;
  phase: MarketTrendStage;
  highlightedStocks: MarketTrendHighlightStock[];
  /** 同题材被归并的板名（零请求名称粗筛），无归并时不出现 */
  relatedPlates?: string[];
};

export type MarketTrendStockTag = {
  lbc: number;
  status: string;
  analysis?: string;
  plate?: string;
};

export type MarketTrendSampleStats = {
  baseCount: number;
  eventAddedCount: number;
  finalCount: number;
};

export type MarketTrendPanelData = {
  range: 10 | 20 | 60;
  latestDay: string;
  topics: MarketTrendTopic[];
  stockTags: Record<string, MarketTrendStockTag>;
  sampleStats: MarketTrendSampleStats;
  /** 近几日曾为候选、今日跌出的板块（本地 IDB 每日留痕，消除幸存者偏差） */
  droppedBoards?: Array<{ name: string; lastSeen: string }>;
};

export type RelayLeader = {
  name: string;
  code: string;
  height: number;
  themes?: string[];
};

/** 断板日首板的事后走势（回看确认） */
export type RelaySuccessor = {
  name: string;
  code: string;
  themes?: string[];
  /** 首板之后达到的最高连板数 */
  maxHeight: number;
  /** 次日 1进2 确认 */
  confirmed: boolean;
  /** 走出 ≥3 板，成为接力龙头 */
  becameLeader: boolean;
};

/** 一次空间龙头断板事件（回看视角） */
export type RelayChainLink = {
  /** 断板日 YYYY-MM-DD */
  date: string;
  /** 当日断板的前高度龙头 */
  leaders: RelayLeader[];
  /** 断板日首板中事后晋级者（≥2板），按高度排序 */
  successors: RelaySuccessor[];
};

/** 今日断板的前高度龙头（盘中 = 暂未封板，盘后 = 断板确认） */
export type RelayBreak = {
  name: string;
  code: string;
  height: number;
  /** zb=今日已炸板（断板基本确认）；absent=暂未见涨停 */
  status: 'zb' | 'absent';
  themes?: string[];
};

/** 断板日首板缩圈候选（盘中/盘后实时评分） */
export type RelayCandidate = {
  breakdown?: Record<string, number>;
  name: string;
  code: string;
  score: number;
  reasons: string[];
  sameTheme: boolean;
  themes?: string[];
  sealTime: string;
  /** 亿元 */
  fund: number;
  price: number | null;
  turnoverRate?: number;
};

/** 今日反包股：前一轮 lbc≥2，断 ≥1 日后回封 */
/** 异动反包分组：连板/首板来自当日异动，炸板回封承接其余当日或昨日炸板 */
export type ReboundPattern = '连板反包' | '首板反包' | '炸板回封';

/** 异动反包候选（分组=形态；确认/临封/修复等为当天状态） */
export type ReboundPick = {
  name: string;
  code: string;
  pattern: ReboundPattern;
  themes?: string[];
  /** 前高（最后一次涨停日的连板高度；今日首板炸板无历史时记 1） */
  prevHeight: number;
  /** 上次涨停后的完整未涨停交易日数，不含今天 */
  gapDays: number;
  /** 回看窗口内是否找到上次涨停；炸板组没有时不展示前高/断板标签 */
  hasPriorSeal?: boolean;
  /** 参与价值评分（组内排序用） */
  score: number;
  /** 评分理由（短标签） */
  reasons: string[];
  /** 前轮曾是当日空间龙头 */
  wasLeader: boolean;
  /** 属于当日主线题材 */
  inMainline: boolean;
  /** 今日炸板 */
  brokeToday?: boolean;
  /** 昨日炸板 */
  brokeYesterday?: boolean;
  /** 当日炸板次数 */
  zbc?: number;
  /** 回封时间（已回封状态） */
  sealTime?: string;
  /** 封单额（亿元，已回封状态） */
  fund?: number;
  price?: number | null;
  /** 换手率% */
  turnoverRate?: number | null;
  /** 实时涨幅%（未回封状态，行情缺失为 null） */
  change?: number | null;
  /** 异动池文案 */
  analysis?: string;
  /** 炸板回封的洗盘时长（分钟，回封时刻−首次炸板时刻） */
  washMinutes?: number;
  /** 因子分项分值（键 = 策略权重键名），校准器样本用 */
  breakdown?: Record<string, number>;
};

/** 单形态历史继续率（回封次日仍在涨停池的比例样本） */
export type ReboundTierStats = { total: number; continued: number };

export type RelaySnapshot = {
  /** 统计窗口内交易日数 */
  days: number;
  /** 最近的断板→接力事件（回看，含失败接力） */
  chain: RelayChainLink[];
  /** 今日仍涨停的高位股（存活的潜在龙头） */
  aliveLeaders: RelayLeader[];
  /** 今日断板（或盘中未封板）的前高度龙头 */
  breaksToday: RelayBreak[];
  /** breaksToday 非空时的首板缩圈名单 */
  watchlist: RelayCandidate[];
  /** 异动反包三组中今日已回封的候选，按参与价值排序 */
  reboundConfirmed: ReboundPick[];
  /** 异动反包三组中未回封候选，盘中挂实时涨幅 */
  reboundWatching: ReboundPick[];
  /** 分形态历史继续率（回封次日仍在涨停池；窗口内、不含今日） */
  reboundStats: {
    /** 连板断板反包（前高≥2，断≥1日回封） */
    rebreak: ReboundTierStats;
    /** 首板断板反包（前高=1，断≥1日回封） */
    firstBoard: ReboundTierStats;
    /** 炸板回封（当日炸板后回封） */
    reseal: ReboundTierStats;
  };
  /** 今日晋级率（昨涨停→今仍涨停），0-100；无昨日数据为 null */
  promoteRate: number | null;
  /** 今日首板家数 */
  firstBoardCount: number;
};

export type MarketSnapshot = {
  diagnostics: Record<MarketCardLabel, MarketCardData>;
  emotionSeries: MarketEmotionPoint[];
  intradayEmotion: IntradayEmotionSnapshot | null;
  payoffLists: {
    strong: MarketPayoffItem[];
    hot: MarketPayoffItem[];
    bigface: MarketPayoffItem[];
  };
  shortEmotion: ShortEmotionSnapshot | null;
  mainlineLanes: MarketMainlineLane[];
  turnover: TurnoverSnapshot | null;
  sectorTrend: MarketTrendPanelData;
  relay: RelaySnapshot | null;
};

export const DEFAULT_MARKET_SNAPSHOT: MarketSnapshot = {
  diagnostics: {
    趋势: { facts: ['当前成交 --', '预估全天 --', '较昨日 --'] },
    情绪: { facts: ['最高板 --', '次高板 --', '最高板家数 --'] },
    主线: { facts: ['资金第一 --', '资金第二 --', '龙头股 --'] },
    赚钱效应: { facts: ['强势股 --', '热榜股 --', '大面代表 --'] },
  },
  emotionSeries: [],
  intradayEmotion: null,
  payoffLists: {
    strong: [],
    hot: [],
    bigface: [],
  },
  shortEmotion: null,
  mainlineLanes: [],
  turnover: null,
  sectorTrend: {
    range: 20,
    latestDay: '',
    topics: [],
    stockTags: {},
    sampleStats: {
      baseCount: 0,
      eventAddedCount: 0,
      finalCount: 0,
    },
  },
  relay: null,
};
