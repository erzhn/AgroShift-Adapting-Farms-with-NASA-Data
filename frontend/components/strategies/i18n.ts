// Тексты модуля «Стратегии и деньги»: русский и английский (для жюри).
// Язык берётся из localStorage["agroshift.lang"] или <html lang>; оболочка может менять его
// событием window.dispatchEvent(new Event("agroshift:lang")).

import { useEffect, useState } from "react";

import { STORAGE_KEYS } from "../../lib/api/strategies";

export type Lang = "ru" | "en";

const ru = {
  title: "Варианты будущего",
  lead: "Перебираем допустимые схемы посева на 30 годах погоды и показываем лучшие по каждой цели — рядом с вашим текущим планом.",
  build: "Построить варианты будущего",
  rebuild: "Пересчитать",
  stages: ["Климат", "Вода", "Оптимизация", "Проверка"],
  stubNote: "Демо-данные: пока модули хозяйства и воды не подключены, расчёт идёт на встроенной заглушке. Это не данные NASA.",
  checked: (n: number, years: number) => `Проверено схем: ${n} · лет погоды: ${years}`,
  type: {
    income: "Больше дохода",
    resilient: "Пережить плохой год",
    water_light: "Меньше воды",
    user: "Мой вариант",
  },
  merged: "Одна схема лучшая сразу по нескольким целям",
  incomeYear: "Доход за год, медиана",
  range: "в плохой — хороший год",
  noGap: "Денег хватает весь год",
  gapIn: (m: string) => `Деньги кончаются: ${m}`,
  gapChance: (p: string) => `риск разрыва ${p}`,
  flags: {
    cash_gap_risk: "Риск кассового разрыва",
    depends_on_conditions: "Лучший вариант зависит от условий",
    experimental: "Экспериментальная схема",
    incomplete: "Расчёт неполный",
    no_buyer: "Часть урожая без покупателя",
    rotation_violation: "Нарушен севооборот",
    needs_financing: "Нужен кредит",
  } as Record<string, string>,
  financing: (s: string, m: string | null) =>
    m ? `Держит резерв, если привлечь ${s} к ${m}` : `Держит резерв, если привлечь ${s}`,
  fixedFinancing: (s: string, m: string | null) =>
    `Смены культур мало: чтобы план выдержал, нужно привлечь ${s}${m ? ` к ${m}` : ""}`,
  monthsTo: ["январю", "февралю", "марту", "апрелю", "маю", "июню", "июлю", "августу", "сентябрю", "октябрю", "ноябрю", "декабрю"],
  excluded: (t: string, p: string, limit: string) =>
    `«${t}» не построена: ни одна схема не держит резерв семьи — лучший риск разрыва ${p} при допустимых ${limit}.`,
  excludedNeed: (s: string) => ` Не хватает около ${s}.`,
  compare: "Сравнение стратегий",
  row: {
    income: "Доход за год (плохой · обычный · хороший год)",
    cvar: "Средний доход в худшие 10% лет",
    water: "Вода брутто за сезон",
    peak: "Вода в пиковые декады",
    worst: "Худшая декада по воде",
    gap: "Кассовый разрыв",
    invest: "Вложения",
    feed: "Свой корм",
    loss: "Потеря урожая на худшем поле",
    unsold: "Без покупателя",
    agro: "Агрономическая проверка",
  },
  approved: "утверждено",
  experimental: "экспериментально",
  none: "нет",
  money: "Деньги по месяцам",
  moneyHint: "Остаток на конец месяца. Полоса — от плохого года (P10) до хорошего (P90).",
  reserve: "Резерв семьи",
  median: "Обычный год",
  band: "Плохой — хороший год",
  gapMark: "Разрыв",
  stress: "Стресс-тест",
  stressLead: "Подвигайте условия и посмотрите, выдержит ли план.",
  presets: "Готовые сценарии",
  reset: "Сбросить",
  slider: {
    water: "Подача воды",
    shift: "Сдвиг подачи",
    temp: "Температура",
    precip: "Осадки",
    price: "Цена продукции",
    feed: "Цена корма",
    delay: "Задержка оплаты",
    yield: "Урожайность",
  },
  days: "дн.",
  preset: {
    hot2023: "Как 2023 год (жара)",
    lowSnow: "Малоснежная зима",
    waterJulAug: "Вода −20% в июле–августе",
    feed40: "Корм +40%",
    delay60: "Оплата +60 дней",
  },
  q: {
    water: "В какой декаде не хватает воды",
    field: "Какой участок самый уязвимый",
    cash: "Когда наступает кассовый разрыв",
    feed: "Что с кормом и сбытом",
    fix: "Что помогает и сколько стоит",
  },
  noWaterDeficit: "Воды хватает",
  noLoss: "Потерь урожая нет",
  lossOf: (p: string) => `потеря урожая ${p}`,
  deficitOf: (v: string) => `не хватает ${v}`,
  needMoney: (s: string) => `не хватает ${s}`,
  feedExtra: (s: string) => `Покупка корма дороже на ${s}`,
  feedSame: "Корм без изменений",
  unsoldT: (t: string) => `${t} т без покупателя`,
  original: "Исходный план",
  fixed: "Исправленный план",
  inNew: "в новых условиях",
  noFixNeeded: "План выдерживает — исправлять не нужно",
  adaptation: "Цена адаптации",
  damage: "Ущерб от условий",
  gain: "Исправление возвращает",
  gainNeg: "Устойчивость стоит дохода",
  changeCost: "Стоимость изменений",
  cheaper: "дешевле исходного",
  baseLine: "Без стресса",
  elapsed: (ms: number) => `пересчитано за ${ms} мс`,
  breakpoints: "Где план сломается",
  breakLead: "Минимальное изменение каждого условия, при котором обычный год нарушает ограничение. Сверху — самое близкое.",
  factor: {
    water_supply_factor: "Подача воды",
    supply_shift_days: "Подача позже",
    temp_delta_c: "Потепление",
    precip_factor: "Осадки",
    feed_price_factor: "Цена корма",
    payment_delay_days: "Задержка оплаты",
    yield_factor: "Урожайность",
    price: "Цена",
  } as Record<string, string>,
  breaks: { cash_gap: "кассовый разрыв", yield_loss: "потеря урожая больше 25%" },
  wasIn: (n: number, of: number) => `было в ${n} из ${of} лет`,
  neverIn: (of: number) => `за ${of} лет не случалось`,
  margin: "Запас",
  holds: "В проверенном диапазоне не ломают план",
  brokenAtBase: (what: string) => `План нарушает ограничение уже в обычных условиях: ${what}. Сначала выберите вариант, который держит резерв.`,
  loading: "Считаем…",
  error: "Не удалось получить расчёт",
  months: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
  monthsFull: ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
  decade: (n: number, m: string) => `${n}-я декада, ${m}`,
  som: "сом",
  thousand: "тыс.",
  million: "млн",
  selected: "Выбрана",
  select: "Выбрать",
  empty: "Нажмите кнопку — система проверит все схемы и покажет до четырёх стратегий.",
};

const en: typeof ru = {
  title: "Future options",
  lead: "We test every allowed cropping scheme against 30 years of weather and show the best one for each goal next to your current plan.",
  build: "Build future options",
  rebuild: "Recalculate",
  stages: ["Climate", "Water", "Optimisation", "Check"],
  stubNote: "Demo data: until the farm and water modules are connected, the built-in stub is used. This is not NASA data.",
  checked: (n, years) => `Schemes checked: ${n} · weather years: ${years}`,
  type: {
    income: "More income",
    resilient: "Survive a bad year",
    water_light: "Less water",
    user: "My plan",
  },
  merged: "One scheme is best for several goals at once",
  incomeYear: "Yearly income, median",
  range: "bad to good year",
  noGap: "Cash lasts all year",
  gapIn: (m) => `Cash runs out: ${m}`,
  gapChance: (p) => `gap risk ${p}`,
  flags: {
    cash_gap_risk: "Cash gap risk",
    depends_on_conditions: "Best option depends on conditions",
    experimental: "Experimental scheme",
    incomplete: "Incomplete calculation",
    no_buyer: "Part of harvest has no buyer",
    rotation_violation: "Rotation rule broken",
    needs_financing: "Needs a loan",
  },
  financing: (s, m) => (m ? `Holds the reserve with ${s} raised by ${m}` : `Holds the reserve with ${s} raised`),
  fixedFinancing: (s, m) =>
    `Changing crops is not enough: the plan holds only with ${s} raised${m ? ` by ${m}` : ""}`,
  monthsTo: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  excluded: (t, p, limit) =>
    `“${t}” was not built: no scheme keeps the family reserve — best gap risk is ${p}, allowed ${limit}.`,
  excludedNeed: (s) => ` About ${s} is missing.`,
  compare: "Strategy comparison",
  row: {
    income: "Yearly income (bad · normal · good year)",
    cvar: "Average income in the worst 10% of years",
    water: "Gross water per season",
    peak: "Water in peak decades",
    worst: "Worst decade for water",
    gap: "Cash gap",
    invest: "Investment",
    feed: "Own feed",
    loss: "Yield loss on the worst field",
    unsold: "No buyer",
    agro: "Agronomist check",
  },
  approved: "approved",
  experimental: "experimental",
  none: "none",
  money: "Cash by month",
  moneyHint: "Balance at month end. The band runs from a bad year (P10) to a good one (P90).",
  reserve: "Family reserve",
  median: "Normal year",
  band: "Bad to good year",
  gapMark: "Gap",
  stress: "Stress test",
  stressLead: "Move the conditions and see whether the plan holds.",
  presets: "Ready scenarios",
  reset: "Reset",
  slider: {
    water: "Water supply",
    shift: "Supply shift",
    temp: "Temperature",
    precip: "Precipitation",
    price: "Product price",
    feed: "Feed price",
    delay: "Payment delay",
    yield: "Yield",
  },
  days: "d",
  preset: {
    hot2023: "Like 2023 (heat)",
    lowSnow: "Low-snow winter",
    waterJulAug: "Water −20% in Jul–Aug",
    feed40: "Feed +40%",
    delay60: "Payment +60 days",
  },
  q: {
    water: "Which decade lacks water",
    field: "Most vulnerable field",
    cash: "When the cash gap comes",
    feed: "Feed and sales",
    fix: "What helps and what it costs",
  },
  noWaterDeficit: "Enough water",
  noLoss: "No yield loss",
  lossOf: (p) => `yield loss ${p}`,
  deficitOf: (v) => `short by ${v}`,
  needMoney: (s) => `short by ${s}`,
  feedExtra: (s) => `Feed purchase costs ${s} more`,
  feedSame: "Feed unchanged",
  unsoldT: (t) => `${t} t without a buyer`,
  original: "Original plan",
  fixed: "Fixed plan",
  inNew: "in the new conditions",
  noFixNeeded: "The plan holds — no fix needed",
  adaptation: "Price of adaptation",
  damage: "Damage from conditions",
  gain: "The fix brings back",
  gainNeg: "Resilience costs income",
  changeCost: "Cost of changes",
  cheaper: "cheaper than the original",
  baseLine: "No stress",
  elapsed: (ms) => `recalculated in ${ms} ms`,
  breakpoints: "Where the plan breaks",
  breakLead: "The smallest change of each condition at which a normal year breaks a constraint. Closest first.",
  factor: {
    water_supply_factor: "Water supply",
    supply_shift_days: "Supply later",
    temp_delta_c: "Warming",
    precip_factor: "Precipitation",
    feed_price_factor: "Feed price",
    payment_delay_days: "Payment delay",
    yield_factor: "Yield",
    price: "Price",
  },
  breaks: { cash_gap: "cash gap", yield_loss: "yield loss above 25%" },
  wasIn: (n, of) => `happened in ${n} of ${of} years`,
  neverIn: (of) => `never in ${of} years`,
  margin: "Margin",
  holds: "Do not break the plan in the tested range",
  brokenAtBase: (what) => `The plan already breaks a constraint in normal conditions: ${what}. Pick an option that keeps the reserve first.`,
  loading: "Calculating…",
  error: "Could not get the calculation",
  months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  monthsFull: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  decade: (n, m) => `decade ${n}, ${m}`,
  som: "KGS",
  thousand: "k",
  million: "M",
  selected: "Selected",
  select: "Select",
  empty: "Press the button — the system checks every scheme and shows up to four strategies.",
};

export type Dict = typeof ru;
export const DICT: Record<Lang, Dict> = { ru, en };

function readLang(): Lang {
  if (typeof window === "undefined") return "ru";
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(STORAGE_KEYS.lang);
  } catch {
    // хранилище недоступно — берём язык страницы
  }
  const value = stored ?? document.documentElement.lang;
  return value?.toLowerCase().startsWith("en") ? "en" : "ru";
}

export function useLang(): [Lang, Dict, (lang: Lang) => void] {
  const [lang, setLang] = useState<Lang>("ru");
  useEffect(() => {
    const sync = () => setLang(readLang());
    sync();
    window.addEventListener("agroshift:lang", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("agroshift:lang", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const change = (next: Lang) => {
    try {
      window.localStorage.setItem(STORAGE_KEYS.lang, next);
    } catch {
      // без хранилища язык живёт до перезагрузки
    }
    setLang(next);
    window.dispatchEvent(new Event("agroshift:lang"));
  };
  return [lang, DICT[lang], change];
}

// --- форматирование чисел ---

export function money(value: number, t: Dict, lang: Lang): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  const locale = lang === "ru" ? "ru-RU" : "en-US";
  if (abs >= 1_000_000) {
    const v = (abs / 1_000_000).toLocaleString(locale, { maximumFractionDigits: 2 });
    return `${sign}${v} ${t.million} ${t.som}`;
  }
  if (abs >= 10_000) {
    return `${sign}${Math.round(abs / 1000).toLocaleString(locale)} ${t.thousand} ${t.som}`;
  }
  return `${sign}${Math.round(abs).toLocaleString(locale)} ${t.som}`;
}

export function volume(m3: number, lang: Lang): string {
  const locale = lang === "ru" ? "ru-RU" : "en-US";
  return `${Math.round(m3).toLocaleString(locale)} ${lang === "ru" ? "м³" : "m³"}`;
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function decadeLabel(decade: number, t: Dict): string {
  const month = Math.floor((decade - 1) / 3);
  return t.decade(((decade - 1) % 3) + 1, t.monthsFull[month]);
}
