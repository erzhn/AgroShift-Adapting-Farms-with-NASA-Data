"use client";

// Верхнее меню экранов модуля воды: возврат на главную и соседние разделы.
// Общая оболочка сайта живёт на главной (сайдбар); здесь — те же переходы строкой.

import { type Lang, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  lang: Lang;
  current?: "nasa";
  farmId?: string | null;
}

export default function WaterNav({ lang, current, farmId }: Props) {
  const t = strings(lang);
  const q = `?lang=${lang}`;
  const strategies = farmId ? `/strategies?farm=${encodeURIComponent(farmId)}&lang=${lang}`
    : `/strategies${q}`;
  return (
    <nav className={css.nav} aria-label={t.navLabel}>
      <a className={css.navBrand} href="/">AgroShift</a>
      <a className={css.navLink} href="/">{t.navHome}</a>
      <a className={css.navLink} href={strategies}>{t.navStrategies}</a>
      <a className={css.navLink} href="/canal">{t.navCanal}</a>
      <a className={css.navLink} href={`/nasa${q}`}
         aria-current={current === "nasa" ? "page" : undefined}>{t.navNasa}</a>
    </nav>
  );
}
