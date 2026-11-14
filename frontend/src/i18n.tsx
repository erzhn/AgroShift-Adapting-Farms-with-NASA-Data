"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Language = "ru" | "en";
type I18nState = { language: Language; changeLanguage: (language: string) => void };

const resources: Record<Language, { translation: Record<string, string> }> = {
    ru: {
      translation: {
        title: "Совместное управление водой",
        navAwp: "Кабинет АВП",
        navField: "Водный баланс поля",
        navNasa: "Данные NASA",
        navStrategies: "Варианты будущего",
        subtitle: "План канала и хозяйства, которые зависят от общей подачи",
        canal: "Канал",
        season: "Сезон",
        farms: "Хозяйства в канале",
        waterPeak: "Пиковый дефицит",
        waterGain: "Изменение пика",
        supply: "Подача по декадам",
        saveSupply: "Сохранить график",
        supplyIncomplete: "Заполните объём подачи для всех 36 декад. Нулевое значение можно указать явно.",
        demandChart: "Спрос и подача по декадам",
        farmsMap: "Хозяйства на канале",
        proposals: "Предложения хозяйствам",
        sources: "Источник: синтетическая демо-подача и расчёты плана",
        noCanals: "Каналы пока не созданы",
        createDemo: "Создать демонстрационный канал",
        noPlan: "Для этого сезона ещё нет расчёта спроса",
        noHydrology: "План строится по симуляциям NASA и оценке урожая хозяйств, давших согласие.",
        calculatePlan: "Рассчитать план",
        planCalculated: "Расчёт завершён. Предложения сохранены.",
        agreeAction: "Согласовать",
        rejectAction: "Отклонить",
        noFarms: "Хозяйства пока не присоединены к каналу",
        decade: "Декада",
        amount: "Подача, м³",
        reliability: "Надёжность",
        status: "Статус",
        planStatus: "План канала",
        change: "Предложение",
        waterChange: "Изменение подачи",
        before: "До координации",
        after: "После координации",
        lowBenefit: "Координация даёт менее 2% выгоды",
        fairnessBlocked: "План не применён: нельзя сохранить справедливое распределение",
        saved: "График подачи сохранён",
        failed: "Не удалось загрузить данные",
        loading: "Загрузка данных…",
        noShift: "Без изменения",
        shift: "Сдвиг сева",
        pending: "Ожидает ответа",
        agree: "Согласен",
        reject: "Не согласен",
        agreed: "Согласован",
        proposed: "На согласовании",
        rejected: "Отклонён",
        unknown: "Неизвестно",
        language: "Язык",
      },
    },
    en: {
      translation: {
        title: "Shared water planning",
        navAwp: "Canal dashboard",
        navField: "Field water balance",
        navNasa: "NASA data",
        navStrategies: "Future scenarios",
        subtitle: "Canal planning for farms that depend on the same water supply",
        canal: "Canal",
        season: "Season",
        farms: "Farms on canal",
        waterPeak: "Peak deficit",
        waterGain: "Peak change",
        supply: "Supply by decade",
        saveSupply: "Save schedule",
        supplyIncomplete: "Enter a supply volume for all 36 decades. You can explicitly enter zero.",
        demandChart: "Demand and supply by decade",
        farmsMap: "Farms on this canal",
        proposals: "Farm proposals",
        sources: "Source: synthetic demo supply and plan simulations",
        noCanals: "No canals have been created yet",
        createDemo: "Create demo canal",
        noPlan: "No demand calculation for this season yet",
        noHydrology: "The plan uses NASA simulations and crop value estimates for farms that consented.",
        calculatePlan: "Calculate plan",
        planCalculated: "Calculation finished. Proposals were saved.",
        agreeAction: "Agree",
        rejectAction: "Reject",
        noFarms: "No farms are connected to this canal yet",
        decade: "Decade",
        amount: "Supply, m³",
        reliability: "Reliability",
        status: "Status",
        planStatus: "Canal plan",
        change: "Proposal",
        waterChange: "Supply change",
        before: "Before coordination",
        after: "After coordination",
        lowBenefit: "Coordination yields less than 2% gain",
        fairnessBlocked: "Plan not applied: fair allocation could not be maintained",
        saved: "Supply schedule saved",
        failed: "Could not load data",
        loading: "Loading data…",
        noShift: "No change",
        shift: "Shift sowing",
        pending: "Awaiting response",
        agree: "Agree",
        reject: "Reject",
        agreed: "Agreed",
        proposed: "Awaiting agreement",
        rejected: "Rejected",
        unknown: "Unknown",
        language: "Language",
      },
    },
};

const I18nContext = createContext<I18nState | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("ru");
  const value = useMemo<I18nState>(
    () => ({
      language,
      changeLanguage: (next) => setLanguage(next.toLowerCase().startsWith("en") ? "en" : "ru"),
    }),
    [language],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const state = useContext(I18nContext);
  if (!state) throw new Error("useTranslation must be used inside I18nProvider");
  const t = useCallback(
    (key: string) => resources[state.language].translation[key] ?? resources.ru.translation[key] ?? key,
    [state.language],
  );
  return { t, i18n: state };
}
