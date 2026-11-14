"use client";
import { useState, type FormEvent } from "react";
import type { Crop, Field, FieldWrite, Language } from "@/lib/api/farms";
import { cropName, optionalNumber, seasonFor } from "@/lib/farms";
import type { Translate } from "@/lib/i18n";
import Modal from "./Modal";
import Icon from "./Icon";

export default function FieldForm({
  field,
  crops,
  year,
  language,
  t,
  onSave,
  onClose,
  onDelete,
}: {
  field?: Field;
  crops: Crop[];
  year: number;
  language: Language;
  t: Translate;
  onSave: (data: FieldWrite) => Promise<void>;
  onClose: () => void;
  onDelete?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const season = field && seasonFor(field, year);
  const location = field?.location?.coordinates || [74.3, 42.86];
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const data: FieldWrite = {
        name: String(form.get("name") || "").trim(),
        irrigation_method: String(form.get("irrigation")),
      };
      if (!data.name) throw new Error("required");
      if (!field?.geometry) {
        const area = optionalNumber(String(form.get("area")));
        const lon = optionalNumber(String(form.get("lon")));
        const lat = optionalNumber(String(form.get("lat")));
        if (!area || area <= 0) throw new Error("invalidArea");
        if (lon === null || lat === null || Math.abs(lon) > 180 || Math.abs(lat) > 90)
          throw new Error("invalidCoordinates");
        data.area_ha = area;
        data.location = { type: "Point", coordinates: [lon, lat] };
      }
      const variant = String(form.get("variant") || "");
      if (variant) {
        const start = String(form.get("sowing") || "") || null;
        const end = String(form.get("harvest") || "") || null;
        if ((start && end && end < start) || (end && Number(end.slice(0, 4)) !== year))
          throw new Error("invalidDates");
        data.season = { crop_variant_id: variant, year, sowing_date: start, harvest_date: end };
      }
      if (field) {
        if (data.name === field.name) delete data.name;
        if (data.irrigation_method === field.irrigation_method) delete data.irrigation_method;
        if (data.area_ha === field.area_ha) delete data.area_ha;
        if (JSON.stringify(data.location) === JSON.stringify(field.location)) delete data.location;
        if (
          data.season &&
          season &&
          data.season.crop_variant_id === season.crop_variant_id &&
          data.season.sowing_date === season.sowing_date &&
          data.season.harvest_date === season.harvest_date
        )
          delete data.season;
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
        ["required", "invalidNumber", "invalidArea", "invalidCoordinates", "invalidDates"].includes(
          message,
        )
          ? t(message as "required")
          : message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={field ? t("fieldEdit") : t("addField")}
      closeLabel={t("close")}
      onClose={() => !busy && onClose()}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <fieldset disabled={busy}>
            <label>
              {t("fieldName")}
              <input name="name" defaultValue={field?.name} required maxLength={100} autoFocus />
            </label>
            <div className="form-grid">
              <label>
                {t("fieldArea")}
                <input
                  name="area"
                  type="number"
                  min="0.0001"
                  max="1000000"
                  step="any"
                  defaultValue={field?.area_ha}
                  disabled={!!field?.geometry}
                  required
                />
              </label>
              <label>
                {t("irrigation")}
                <select name="irrigation" defaultValue={field?.irrigation_method || "furrow"}>
                  {["furrow", "flood", "sprinkler", "drip", "none"].map((v) => (
                    <option key={v} value={v}>
                      {t(v as "furrow")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {field?.geometry ? (
              <p className="hint">{t("polygonArea")}</p>
            ) : (
              <>
                <div className="form-grid">
                  <label>
                    {t("longitude")}
                    <input
                      name="lon"
                      type="number"
                      min="-180"
                      max="180"
                      step="any"
                      defaultValue={location[0]}
                      required
                    />
                  </label>
                  <label>
                    {t("latitude")}
                    <input
                      name="lat"
                      type="number"
                      min="-90"
                      max="90"
                      step="any"
                      defaultValue={location[1]}
                      required
                    />
                  </label>
                </div>
                <p className="hint">{t("locationHint")}</p>
              </>
            )}
            <label>
              {t("crop")} · {year}
              <select name="variant" defaultValue={season?.crop_variant_id || ""}>
                <option value="" disabled={!!season}>
                  {t("noCrop")}
                </option>
                {crops.flatMap((c) =>
                  c.variants.map((v) => (
                    <option key={v.id} value={v.id}>
                      {cropName(c, language)}
                    </option>
                  )),
                )}
              </select>
            </label>
            <div className="form-grid">
              <label>
                {t("sowingDate")}
                <input name="sowing" type="date" defaultValue={season?.sowing_date || ""} />
              </label>
              <label>
                {t("harvestDate")}
                <input name="harvest" type="date" defaultValue={season?.harvest_date || ""} />
              </label>
            </div>
          </fieldset>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
        <div className="modal-footer">
          {onDelete && (
            <button type="button" className="danger-link" onClick={onDelete} disabled={busy}>
              <Icon name="trash" size={16} />
              {t("delete")}
            </button>
          )}
          <span className="spacer" />
          <button type="button" className="button secondary" onClick={onClose} disabled={busy}>
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
