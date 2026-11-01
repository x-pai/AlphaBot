export type FlowObservation = {
  date: string;
  mainNetInflow: number;
  mainNetInflowRatio: number;
  excluded?: boolean;
};

export function validFlowPoint(point: FlowObservation | undefined): point is FlowObservation {
  return !!point && !point.excluded && Number.isFinite(point.mainNetInflow) && Number.isFinite(point.mainNetInflowRatio);
}

/** Use the same five trading dates for every board; missing days are never treated as zero. */
export function summarizeFlow(points: FlowObservation[], dates: string[]) {
  const byDate = new Map(points.filter(validFlowPoint).map((point) => [point.date, point]));
  const window = dates.slice(-5);
  const available = window.flatMap((date) => byDate.has(date) ? [byDate.get(date)!] : []);
  const complete = window.length === 5 && available.length === 5;
  return {
    availableDays: available.length,
    positiveDays: complete ? available.filter((point) => point.mainNetInflow > 0).length : null,
    netInflow: complete ? available.reduce((sum, point) => sum + point.mainNetInflow, 0) : null,
    latest: byDate.get(dates[dates.length - 1]) ?? null,
  };
}

/** Fixed, symmetric percentage bands keep colors comparable between dates and boards. */
export function flowHeatBand(value: number): -3 | -2 | -1 | 0 | 1 | 2 | 3 {
  const magnitude = Math.abs(value);
  const band = magnitude === 0 ? 0 : magnitude < 3 ? 1 : magnitude < 8 ? 2 : 3;
  return (Math.sign(value) * band) as -3 | -2 | -1 | 0 | 1 | 2 | 3;
}
