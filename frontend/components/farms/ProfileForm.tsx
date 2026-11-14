"use client";
import { useState, type FormEvent } from "react";
import type { Farm, FarmWrite, Language } from "@/lib/api/farms";
import { optionalNumber } from "@/lib/farms";
import type { Translate } from "@/lib/i18n";
import Modal from "./Modal";
import Icon from "./Icon";

export default function ProfileForm({
  farm,
  t,
  onSave,
  onClose,
  onDelete,
}: {
  farm?: Farm;
  t: Translate;
  onSave: (data: FarmWrite) => Promise<void>;
  onClose: () => void;
  onDelete?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const herds = farm?.herds.filter((h) => h.species === "cow" && h.purpose === "milk") || [];
  const count = herds.length ? herds.reduce((sum, h) => sum + h.head_count, 0) : null;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const data: FarmWrite = {
        name: String(form.get("name") || "").trim(),
        district: String(form.get("district") || "").trim() || null,
        village: String(form.get("village") || "").trim() || null,
        language: form.get("language") as Language,
        family_reserve_som: optionalNumber(String(form.get("reserve") || ""), true),
        consent_agronomist: form.has("agronomist"),
        consent_canal_plan: form.has("canal"),
        consent_analytics: form.has("analytics"),
      };
      if (!farm || farm.cash_accounts.length <= 1)
        data.cash_som = optionalNumber(String(form.get("cash") || ""), true);
      if (herds.length <= 1) data.cow_count = optionalNumber(String(form.get("cows") || ""), true);
      if (!data.name) throw new Error("required");
      if ((data.family_reserve_som ?? 0) < 0 || (data.cow_count ?? 0) < 0)
        throw new Error("invalidNumber");
      if (farm) {
        for (const key of Object.keys(data) as (keyof FarmWrite)[]) {
          const previous = key === "cow_count" ? count : farm[key as keyof Farm];
          if (data[key] === previous) delete data[key];
        }
        if (!Object.keys(data).length) {
          onClose();
          return;
        }
      }
      setBusy(true);
      await onSave(data);
    } catch (err) {
      const message = (err as Error).message;
      setError(
        ["required", "invalidNumber"].includes(message) ? t(message as "required") : message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={farm ? t("profile") : t("addFarm")}
      closeLabel={t("close")}
      onClose={() => !busy && onClose()}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <p className="muted">{t("profileHint")}</p>
          <fieldset disabled={busy}>
            <legend>{t("general")}</legend>
            <label>
              {t("name")}
              <input name="name" defaultValue={farm?.name} required maxLength={200} autoFocus />
            </label>
            <div className="form-grid">
              <label>
                {t("district")}
                <input name="district" defaultValue={farm?.district || ""} maxLength={100} />
              </label>
              <label>
                {t("village")}
                <input name="village" defaultValue={farm?.village || ""} maxLength={100} />
              </label>
            </div>
            <label>
              {t("language")}
              <select name="language" defaultValue={farm?.language || "ru"}>
                <option value="ru">Русский</option>
                <option value="ky">Кыргызча</option>
                <option value="en">English</option>
              </select>
            </label>
          </fieldset>
          <fieldset disabled={busy}>
            <legend>{t("financial")}</legend>
            <div className="form-grid">
              <label>
                {t("balance")}
                <input
                  name="cash"
                  type="number"
                  step="1"
                  defaultValue={farm?.cash_som ?? ""}
                  disabled={!!farm && farm.cash_accounts.length > 1}
                />
              </label>
              <label>
                {t("reserve")}
                <input
                  name="reserve"
                  type="number"
                  min="0"
                  step="1"
                  defaultValue={farm?.family_reserve_som ?? ""}
                />
              </label>
            </div>
            <label>
              {t("cowCount")}
              <input
                name="cows"
                type="number"
                min="0"
                max="1000000"
                step="1"
                defaultValue={count ?? ""}
                disabled={herds.length > 1}
              />
            </label>
            <p className="hint">{t("optionalHint")}</p>
          </fieldset>
          <fieldset className="checks" disabled={busy}>
            <legend>{t("consents")}</legend>
            <label>
              <input name="agronomist" type="checkbox" defaultChecked={farm?.consent_agronomist} />
              {t("agronomist")}
            </label>
            <label>
              <input name="canal" type="checkbox" defaultChecked={farm?.consent_canal_plan} />
              {t("canalConsent")}
            </label>
            <label>
              <input name="analytics" type="checkbox" defaultChecked={farm?.consent_analytics} />
              {t("analytics")}
            </label>
          </fieldset>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
        </div>
        <div className="modal-footer">
          {onDelete && (
            <button type="button" className="danger-link" disabled={busy} onClick={onDelete}>
              <Icon name="trash" size={16} />
              {t("delete")}
            </button>
          )}
          <span className="spacer" />
          <button type="button" className="button secondary" disabled={busy} onClick={onClose}>
            {t("cancel")}
          </button>
          <button type="submit" className="button primary" disabled={busy}>
            {busy ? t("saving") : t("save")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
