"use client";

// Экран «Варианты будущего» (UC-2, UC-3): стратегии, сравнение, деньги по месяцам,
// стресс-тест и точки поломки. Хозяйство — из ?farm=<id>, по умолчанию демо.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import BreakpointList from "../../components/strategies/BreakpointList";
import MoneyLane from "../../components/strategies/MoneyLane";
import { CompareTable, StrategyCards } from "../../components/strategies/StrategyCards";
import StressPanel from "../../components/strategies/StressPanel";
import { money, percent, useLang } from "../../components/strategies/i18n";
import css from "../../components/strategies/strategies.module.css";
import {
  type GenerateResponse,
  type Strategy,
  STORAGE_KEYS,
  generateStrategies,
} from "../../lib/api/strategies";

const DEFAULT_FARM = "demo";

function farmFromUrl(): string {
  return new URLSearchParams(window.location.search).get("farm") ?? DEFAULT_FARM;
}

function remember(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // без хранилища выбор живёт до перезагрузки страницы
  }
}

export default function StrategiesPage() {
  const [lang, t, setLang] = useLang();
  const [data, setData] = useState<GenerateResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stage, setStage] = useState(-1); // −1 — не считаем; 0..3 — этап расчёта
  const [error, setError] = useState<string | null>(null);
  const [month, setMonth] = useState<number | undefined>(undefined);
  const timer = useRef<number | undefined>(undefined);

  const build = useCallback(async (farm: string) => {
    setError(null);
    setStage(0);
    window.clearInterval(timer.current);
    timer.current = window.setInterval(() => setStage((s) => Math.min(3, s + 1)), 350);
    try {
      const generated = await generateStrategies(farm);
      setData(generated);
      remember(STORAGE_KEYS.built, farm);
      // по умолчанию — «Мой вариант»: с него начинается разговор о том, что менять
      const first =
        generated.strategies.find((s) => s.types.includes("user")) ?? generated.strategies[0];
      setSelectedId((current) =>
        generated.strategies.some((s) => s.id === current) ? current : (first?.id ?? null),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      window.clearInterval(timer.current);
      setStage(-1);
    }
  }, []);

  useEffect(() => {
    const farm = farmFromUrl();
    let built: string | null = null;
    try {
      built = window.localStorage.getItem(STORAGE_KEYS.built);
    } catch {
      // хранилище недоступно
    }
    // варианты для этого хозяйства уже строили — показываем сразу, без кнопки
    const restore = built === farm ? window.setTimeout(() => build(farm), 0) : undefined;
    return () => {
      window.clearTimeout(restore);
      window.clearInterval(timer.current);
    };
  }, [build]);

  const selected = useMemo(
    () => data?.strategies.find((s) => s.id === selectedId) ?? null,
    [data, selectedId],
  );

  const select = (strategy: Strategy) => {
    setSelectedId(strategy.id);
    remember(STORAGE_KEYS.runId, strategy.run_id);
    window.dispatchEvent(new Event("agroshift:run")); // лента денег на главном экране
  };

  const cropNames = useMemo(() => {
    const names: Record<string, string> = { milk: lang === "ru" ? "Молоко" : "Milk" };
    for (const s of data?.strategies ?? []) {
      for (const d of s.decisions) names[d.crop_id] = lang === "ru" ? d.crop_name_ru : d.crop_name_en;
    }
    return names;
  }, [data, lang]);

  const stub = data && Object.values(data.provenance.inputs_status).includes("stub");
  const busy = stage >= 0;

  return (
    <main className={css.page}>
      <header className={css.header}>
        <div>
          <h1>{t.title}</h1>
          <p className={css.lead}>{t.lead}</p>
        </div>
        <div className={css.actions}>
          <button
            type="button"
            className={css.langButton}
            onClick={() => setLang(lang === "ru" ? "en" : "ru")}
          >
            {lang === "ru" ? "English" : "Русский"}
          </button>
          <button type="button" className={css.primary} disabled={busy} onClick={() => build(farmFromUrl())}>
            {data ? t.rebuild : t.build}
          </button>
        </div>
        {busy && (
          <ol className={css.stages}>
            {t.stages.map((name, i) => (
              <li key={name} data-done={i <= stage}>
                {name}
              </li>
            ))}
          </ol>
        )}
        {error && <p className={css.error}>{t.error}: {error}</p>}
        {stub && <p className={css.note}>{t.stubNote}</p>}
        {data && (
          <p className={css.meta}>
            {data.farm_name} · {t.checked(data.schemes_checked, data.provenance.n_samples)}
          </p>
        )}
      </header>

      {!data && !busy && !error && <p className={css.empty}>{t.empty}</p>}

      {data && (
        <>
          <section className={css.section}>
            <StrategyCards data={data} selectedId={selectedId} onSelect={select} t={t} lang={lang} />
            {data.excluded.map((x) => (
              <p key={x.type} className={css.note}>
                {t.excluded(t.type[x.type], percent(x.best_p_gap), percent(x.p_gap_limit))}
                {x.financing_needed_som > 0 &&
                  t.excludedNeed(money(x.financing_needed_som, t, lang))}
              </p>
            ))}
          </section>

          <section className={css.section}>
            <h2>{t.compare}</h2>
            <CompareTable data={data} selectedId={selectedId} onSelect={select} t={t} lang={lang} />
          </section>

          {selected && (
            <>
              <section className={css.section}>
                <h2>
                  {t.money} · {selected.types.map((k) => t.type[k]).join(" · ")}
                </h2>
                <div className={css.panel}>
                  <MoneyLane runId={selected.run_id} month={month} onMonthChange={setMonth} />
                </div>
              </section>

              <section className={css.section}>
                <h2>{t.stress}</h2>
                <p className={css.muted}>{t.stressLead}</p>
                <StressPanel key={selected.run_id} runId={selected.run_id} t={t} lang={lang} />
              </section>

              <section className={css.section}>
                <h2>{t.breakpoints}</h2>
                <p className={css.muted}>{t.breakLead}</p>
                <BreakpointList
                  key={selected.run_id}
                  runId={selected.run_id}
                  names={cropNames}
                  t={t}
                  lang={lang}
                />
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
