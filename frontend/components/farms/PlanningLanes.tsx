import type { ComponentType } from "react";
import type { Farm, Scenario, Language } from "@/lib/api/farms";
import type { Translate } from "@/lib/i18n";
import Icon from "./Icon";

/** Shared integration seam. WaterLane and MoneyLane remain owned by their modules. */
export interface LaneProps {
  farm: Farm;
  year: number;
  month: number;
  strategyId: string;
  scenario: Scenario | null;
  language?: Language;
  runId?: string;
  onMonthChange?: (month: number) => void;
}
export interface StrategyOption {
  id: string;
  name: string;
}
export interface FarmIntegrations {
  WaterLane?: ComponentType<LaneProps>;
  MoneyLane?: ComponentType<LaneProps>;
  strategies?: StrategyOption[];
}
export default function PlanningLanes({
  context,
  integrations,
  t,
}: {
  context: LaneProps;
  integrations: FarmIntegrations;
  t: Translate;
}) {
  return (
    <div className="planning-lanes">
      {(["water", "money"] as const).map((kind) => {
        const Component = kind === "water" ? integrations.WaterLane : integrations.MoneyLane;
        return (
          <section key={kind} className={`lane lane-${kind}`} aria-label={t(kind)}>
            <div className="lane-icon">
              <Icon name={kind === "water" ? "drop" : "wallet"} />
            </div>
            <div className="lane-content">
              <h3>{t(kind)}</h3>
              {Component ? (
                <Component {...context} />
              ) : (
                <>
                  <p>{t(kind === "water" ? "waterEmpty" : "moneyEmpty")}</p>
                  <span>{t("laneHint")}</span>
                </>
              )}
            </div>
            {!Component && (
              <div className="empty-chart" aria-hidden="true">
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
