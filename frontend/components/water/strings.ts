// Строки экранов модуля «Вода и климат» (раздел 12.4 ТЗ: никакого текста в компонентах).
// Кыргызский пока берёт русские строки: тексты должен вычитать носитель языка
// с агрономическим опытом. При подключении i18next ключи переносятся как есть.

import { useEffect, useState } from "react";

export type Lang = "ru" | "en" | "ky";

const ru = {
  navHome: "← Моё хозяйство",
  navStrategies: "Варианты будущего",
  navCanal: "Кабинет АВП",
  navNasa: "Данные NASA",
  navLabel: "Разделы",
  loading: "Считаем…",
  error: "Не удалось получить данные",
  retry: "Повторить",
  table: "Таблица",
  chart: "График",
  decade: "Декада",
  year: "Год погоды",
  typicalYear: "типичный год",
  typicalYearHint: "медианный по урожаю из 30 лет NASA",
  nasaYears: "лет истории NASA",

  laneTitle: "Вода: потребность и подача",
  laneUnit: "м³ на водовыпуске хозяйства, по декадам",
  need: "Потребность",
  received: "Получено по очереди",
  deficitGe20: "Дефицит ≥ 20 %",
  deficitLt20: "Дефицит < 20 %",
  statusOk: "норма",
  turnsFailed: "сорвано очередей",
  yearsOf: (n: number, total: number) => `так было в ${n} из ${total} лет`,
  thousand: "тыс.",

  passport: "Паспорт поля",
  area: "Площадь",
  ha: "га",
  elevation: "Высота",
  m: "м",
  soil: "Почва",
  irrigation: "Способ полива",
  crop: "Культура",
  sowing: "Сев / начало вегетации",
  farm: "Хозяйство",
  unknown: "неизвестно",
  demoProfile: "Демо-профиль: модуль хозяйств ещё не подключён",

  seasonTitle: "Вода по декадам",
  seasonUnit: "мм за декаду",
  irrigationNet: "Полив (дошло до корней)",
  precip: "Осадки",
  etc: "Потребность культуры ETc",
  et0: "Эталонная ET0",
  shortfall: "Недобор воды (ETc − ETa)",
  eta: "Фактически ETa",
  soilTitle: "Запас влаги в почве",
  soilUnit: "истощение корневой зоны D_r, мм · ниже — суше",
  dr: "Истощение D_r",
  raw: "Граница стресса (RAW)",
  taw: "Предел запаса (TAW)",
  stressZone: "зона стресса",
  noStressZone: "легкодоступная влага",
  ks: "Коэффициент стресса K_s",

  yieldTitle: "Урожай",
  yieldUnit: "т/га",
  modelEstimate: "модельная оценка",
  badYear: "в плохой год",
  usualYear: "в обычный год",
  goodYear: "в хороший год",
  thisYear: (y: number) => `в погоде ${y} года`,
  ofPotential: "от возможного",
  lossByStage: "Потеря урожая от дефицита воды по стадиям",
  mostImportant: "вода важнее всего",
  noLoss: "потерь нет",
  heatLoss: "Жара в цветение",
  frostLoss: "Заморозок в цветение",
  stageNames: { ini: "Начальная", dev: "Развитие", mid: "Середина сезона", late: "Поздняя" },

  totals: "Итог сезона",
  needGross: "Потребность брутто",
  gotByTurn: "Получено по очереди",
  deficit: "Дефицит",
  m3: "м³",
  mm: "мм",
  worstDecade: "Худшая декада",
  timingNote: "За сезон воды подано не меньше потребности, но не в те декады, когда она "
    + "нужна: часть пришла в полную почву, часть очередей сорвалась.",
  alerts: {
    water_deficit: "Дефицит воды",
    frost_in_bloom: "Заморозок в цветение",
    heat_in_flowering: "Жара в цветение",
    resow_risk: "Заморозок по всходам — риск пересева",
  },
  days: "дн.",

  provenance: "Откуда это число",
  provenanceClose: "Закрыть",
  snapshot: "Снимок данных",
  modelVersion: "Версия модели",
  et0Method: "Метод ET0",
  et0Methods: { penman_monteith: "FAO-56 Penman–Monteith", mixed: "Penman–Monteith + Hargreaves",
                hargreaves: "Hargreaves–Samani (упрощённый)" },
  formulas: "Формулы",
  formulaList: [
    "ET0 — FAO-56 Penman–Monteith по суточным данным NASA POWER",
    "ETc = Kc × ET0, Kc — кривая FAO-56 по четырём стадиям",
    "Суточный баланс корневой зоны: D_r, RAW, TAW, K_s",
    "Нетто = брутто × КПД полива; очередь — события раз в N дней",
    "Урожай — FAO-33: произведение множителей по стадиям",
  ],
  inputs: "Входы расчёта",
  incomplete: "Расчёт неполный",
  incompleteHint: "Неизвестные входы заменены справочными значениями, диапазон шире",
  complete: "Все входы известны",
  resolutionNote: "Климат района ~55 × 50 км, а не данные вашего поля",
  cell: "Ячейка NASA POWER",
  kcUsed: "Kc нач. / сер. / кон.",
  sourceTypes: { measured: "измерено", satellite: "спутник", model: "модель",
                 reference: "справочник", user_estimate: "оценка пользователя",
                 unknown: "неизвестно" },
  inputNames: {
    elevation_m: "Высота поля", taw_mm_per_m: "Доступная влага почвы",
    initial_depletion_fraction: "Начальное истощение, доля TAW",
    field_efficiency: "КПД полива на поле", canal_efficiency: "КПД канала",
    turn_interval_days: "Интервал очереди", turn_volume_m3: "Объём одной очереди",
    water_reliability: "Надёжность подачи",
  } as Record<string, string>,
  unknownInputNames: {
    taw: "почва", canal_efficiency: "КПД канала", water_limit: "лимит воды",
    water_reliability: "надёжность подачи", elevation: "высота поля",
    location: "координаты поля",
  } as Record<string, string>,
  units: { m: "м", "mm/m": "мм/м", day: "дн.", m3: "м³" } as Record<string, string>,
  mapHelp: "Ctrl + прокрутка — масштаб карты",
  mapHelpMobile: "Двигайте карту двумя пальцами",
  irrigationMethods: { furrow: "бороздковый", flood: "напуск", sprinkler: "дождевание",
                       drip: "капельный", none: "без полива" } as Record<string, string>,
  soils: { loam: "суглинок", sandy_loam: "супесь", serozem: "серозём", clay: "глина",
           clay_loam: "тяжёлый суглинок", silt_loam: "пылеватый суглинок",
           sand: "песок" } as Record<string, string>,

  nasaTitle: "Данные NASA",
  nasaLead: "Данные NASA — вход расчётного ядра: климат → эвапотранспирация → потребность "
    + "культур в воде → водный баланс → урожай.",
  offline: "Расчёты идут по локальным снимкам — работает без интернета",
  datasets: "Наборы данных",
  used: "используется",
  planned: "в планах",
  parameters: "Параметры",
  resolution: "Разрешение",
  frequency: "Частота",
  usedFor: "Для чего",
  limitations: "Ограничения",
  snapshots: "Снимки NASA POWER",
  snapshotsHint: "Неизменяемые версии данных: расчёт ссылается на снимок, а не на «живой» API",
  point: "Точка",
  coords: "Координаты",
  period: "Период",
  fetched: "Дата снимка",
  rows: "Суток",
  missing: "Пропусков",
  version: "Версия API",
  checksum: "sha256",
  cellElevation: "Высота ячейки",
  gridTitle: "Ячейки сетки NASA POWER",
  gridHint: "Метеоданные приходят по ячейке 0,5° × 0,625°. Это климат района, а не поля; "
    + "температура поправляется на высоту поля.",
  attribution: "Атрибуция",
  mapFallback: "Карта-подложка недоступна без сети — ячейки и точки показаны поверх фона",
};

type Strings = typeof ru;

const en: Strings = {
  ...ru,
  navHome: "← My farm",
  navStrategies: "Future options",
  navCanal: "Water users office",
  navNasa: "NASA data",
  navLabel: "Sections",
  loading: "Calculating…",
  error: "Could not load data",
  retry: "Retry",
  table: "Table",
  chart: "Chart",
  decade: "Decade",
  year: "Weather year",
  typicalYear: "typical year",
  typicalYearHint: "median by yield across 30 years of NASA data",
  nasaYears: "years of NASA history",
  laneTitle: "Water: need vs supply",
  laneUnit: "m³ at the farm outlet, by 10-day period",
  need: "Need",
  received: "Received by turn",
  deficitGe20: "Deficit ≥ 20%",
  deficitLt20: "Deficit < 20%",
  statusOk: "ok",
  turnsFailed: "turns missed",
  yearsOf: (n, total) => `this happened in ${n} of ${total} years`,
  thousand: "k",
  passport: "Field profile",
  area: "Area",
  ha: "ha",
  elevation: "Elevation",
  m: "m",
  soil: "Soil",
  irrigation: "Irrigation method",
  crop: "Crop",
  sowing: "Sowing / season start",
  farm: "Farm",
  unknown: "unknown",
  demoProfile: "Demo profile: the farms module is not connected yet",
  seasonTitle: "Water by 10-day period",
  seasonUnit: "mm per period",
  irrigationNet: "Irrigation (reached roots)",
  precip: "Precipitation",
  etc: "Crop need ETc",
  et0: "Reference ET0",
  shortfall: "Water shortfall (ETc − ETa)",
  eta: "Actual ETa",
  soilTitle: "Soil water",
  soilUnit: "root-zone depletion D_r, mm · lower is drier",
  dr: "Depletion D_r",
  raw: "Stress threshold (RAW)",
  taw: "Storage limit (TAW)",
  stressZone: "stress zone",
  noStressZone: "readily available water",
  ks: "Stress coefficient K_s",
  yieldTitle: "Yield",
  yieldUnit: "t/ha",
  modelEstimate: "model estimate",
  badYear: "in a bad year",
  usualYear: "in a usual year",
  goodYear: "in a good year",
  thisYear: (y) => `in ${y} weather`,
  ofPotential: "of potential",
  lossByStage: "Yield loss from water deficit by stage",
  mostImportant: "water matters most",
  noLoss: "no loss",
  heatLoss: "Heat during flowering",
  frostLoss: "Frost during bloom",
  stageNames: { ini: "Initial", dev: "Development", mid: "Mid-season", late: "Late" },
  totals: "Season total",
  needGross: "Gross need",
  gotByTurn: "Received by turn",
  deficit: "Deficit",
  m3: "m³",
  mm: "mm",
  worstDecade: "Worst period",
  timingNote: "Over the season the supply is not below the need, but it came in the wrong "
    + "periods: some arrived when the soil was full, some turns were missed.",
  alerts: {
    water_deficit: "Water deficit",
    frost_in_bloom: "Frost during bloom",
    heat_in_flowering: "Heat during flowering",
    resow_risk: "Frost on seedlings — resowing risk",
  },
  days: "d",
  provenance: "Where this number comes from",
  provenanceClose: "Close",
  snapshot: "Data snapshot",
  modelVersion: "Model version",
  et0Method: "ET0 method",
  et0Methods: { penman_monteith: "FAO-56 Penman–Monteith", mixed: "Penman–Monteith + Hargreaves",
                hargreaves: "Hargreaves–Samani (simplified)" },
  formulas: "Formulas",
  formulaList: [
    "ET0 — FAO-56 Penman–Monteith on NASA POWER daily data",
    "ETc = Kc × ET0, Kc — FAO-56 four-stage curve",
    "Daily root-zone balance: D_r, RAW, TAW, K_s",
    "Net = gross × irrigation efficiency; turns are events every N days",
    "Yield — FAO-33: product of stage multipliers",
  ],
  inputs: "Calculation inputs",
  incomplete: "Incomplete calculation",
  incompleteHint: "Unknown inputs are replaced by reference values, the range is wider",
  complete: "All inputs are known",
  resolutionNote: "District climate ~55 × 50 km, not data of your field",
  cell: "NASA POWER cell",
  kcUsed: "Kc ini / mid / end",
  sourceTypes: { measured: "measured", satellite: "satellite", model: "model",
                 reference: "reference", user_estimate: "user estimate", unknown: "unknown" },
  inputNames: {
    elevation_m: "Field elevation", taw_mm_per_m: "Available soil water",
    initial_depletion_fraction: "Initial depletion, share of TAW",
    field_efficiency: "Field irrigation efficiency", canal_efficiency: "Canal efficiency",
    turn_interval_days: "Turn interval", turn_volume_m3: "Volume per turn",
    water_reliability: "Supply reliability",
  },
  unknownInputNames: {
    taw: "soil", canal_efficiency: "canal efficiency", water_limit: "water limit",
    water_reliability: "supply reliability", elevation: "field elevation",
    location: "field coordinates",
  },
  units: { m: "m", "mm/m": "mm/m", day: "d", m3: "m³" },
  mapHelp: "Use Ctrl + scroll to zoom the map",
  mapHelpMobile: "Use two fingers to move the map",
  irrigationMethods: { furrow: "furrow", flood: "flood", sprinkler: "sprinkler", drip: "drip",
                       none: "rainfed" },
  soils: { loam: "loam", sandy_loam: "sandy loam", serozem: "serozem", clay: "clay",
           clay_loam: "clay loam", silt_loam: "silt loam", sand: "sand" },
  nasaTitle: "NASA data",
  nasaLead: "NASA data is the input of the calculation core: climate → evapotranspiration → "
    + "crop water need → water balance → yield.",
  offline: "Calculations run on local snapshots — works offline",
  datasets: "Datasets",
  used: "in use",
  planned: "planned",
  parameters: "Parameters",
  resolution: "Resolution",
  frequency: "Frequency",
  usedFor: "Used for",
  limitations: "Limitations",
  snapshots: "NASA POWER snapshots",
  snapshotsHint: "Immutable data versions: a calculation refers to a snapshot, not the live API",
  point: "Point",
  coords: "Coordinates",
  period: "Period",
  fetched: "Snapshot date",
  rows: "Days",
  missing: "Missing",
  version: "API version",
  checksum: "sha256",
  cellElevation: "Cell elevation",
  gridTitle: "NASA POWER grid cells",
  gridHint: "Weather data comes per 0.5° × 0.625° cell. It is district climate, not field "
    + "data; temperature is corrected for field elevation.",
  attribution: "Attribution",
  mapFallback: "Basemap is unavailable offline — cells and points are drawn over a plain background",
};

const STRINGS: Record<Lang, Strings> = { ru, en, ky: ru };

export function strings(lang: Lang): Strings {
  return STRINGS[lang] ?? ru;
}

const MONTHS: Record<Lang, string[]> = {
  ru: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  ky: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
};
const PARTS = ["I", "II", "III"];

export function monthShort(month1: number, lang: Lang): string {
  return (MONTHS[lang] ?? MONTHS.ru)[month1 - 1];
}

/** Декада 1..36 -> «июл III». */
export function decadeLabel(decade: number, lang: Lang): string {
  const month0 = Math.floor((decade - 1) / 3);
  return `${monthShort(month0 + 1, lang)} ${PARTS[(decade - 1) % 3]}`;
}

export function formatNumber(value: number, lang: Lang, digits = 0): string {
  return new Intl.NumberFormat(lang === "en" ? "en-US" : "ru-RU",
    { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

/** «14 ноября 2026 г.»; withYear = false -> «1 мая» (год погоды условный). */
export function formatDate(iso: string, lang: Lang, withYear = true): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat(lang === "en" ? "en-US" : "ru-RU", {
    day: "numeric", month: "long", year: withYear ? "numeric" : undefined, timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

/** Язык интерфейса: ?lang=, затем <html lang>, затем русский. */
export function useLang(explicit?: Lang): Lang {
  const [lang, setLang] = useState<Lang>(explicit ?? "ru");
  useEffect(() => {
    if (explicit) { setLang(explicit); return; }
    const fromQuery = new URLSearchParams(window.location.search).get("lang");
    const candidate = (fromQuery ?? document.documentElement.lang ?? "ru").slice(0, 2);
    setLang(candidate === "en" || candidate === "ky" ? candidate : "ru");
  }, [explicit]);
  return lang;
}
