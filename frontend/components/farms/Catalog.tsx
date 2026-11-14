import type { Crop, Language, Rotation } from "@/lib/api/farms";
import { colors, cropName } from "@/lib/farms";
import { locales, type Translate } from "@/lib/i18n";
import Icon from "./Icon";

export default function Catalog({
  crops,
  rotations,
  language,
  t,
}: {
  crops: Crop[];
  rotations: Rotation[];
  language: Language;
  t: Translate;
}) {
  const number = (n: number | undefined) =>
    n === undefined ? "—" : n.toLocaleString(locales[language], { maximumFractionDigits: 2 });
  return (
    <div className="catalog">
      <div className="page-heading">
        <div>
          <div className="eyebrow">AGROSHIFT / DATA</div>
          <h1>{t("catalog")}</h1>
          <p>{t("catalogIntro")}</p>
        </div>
      </div>
      <div className="crop-cards">
        {crops.map((crop) => (
          <article className="crop-card" key={crop.id}>
            <header>
              <span
                className="crop-symbol"
                style={{ color: colors[crop.code], background: `${colors[crop.code]}18` }}
              >
                <Icon name="leaf" size={25} />
              </span>
              <div>
                <h2>{cropName(crop, language)}</h2>
                <span className="badge">{t("reference")}</span>
              </div>
            </header>
            <dl>
              <div>
                <dt>Kc · ini / mid / end</dt>
                <dd>{[crop.kc_ini, crop.kc_mid, crop.kc_end].map(number).join(" / ")}</dd>
              </div>
              <div>
                <dt>{t("stages")}</dt>
                <dd>{crop.stage_days.join(" / ")}</dd>
              </div>
              <div>
                <dt>{t("root")}</dt>
                <dd>{number(crop.root_depth_m)}</dd>
              </div>
              <div>
                <dt>p / Ky</dt>
                <dd>
                  {number(crop.p_depletion)} / {number(crop.ky)}
                </dd>
              </div>
              <div>
                <dt>{t("yield")}</dt>
                <dd>
                  {number(crop.variants[0]?.yield_potential_t_ha)} <small>{t("estimate")}</small>
                </dd>
              </div>
              <div>
                <dt>{t("price")}</dt>
                <dd>
                  {crop.price ? number(crop.price.price_som) : "—"} <small>{t("estimate")}</small>
                </dd>
              </div>
            </dl>
            <details>
              <summary>{t("source")}</summary>
              <div className="sources">
                {Object.entries(crop.provenance)
                  .filter(([key]) => ["kc_mid", "stage_days", "root_depth_m", "ky"].includes(key))
                  .map(([key, source]) => (
                    <p key={key}>
                      <strong>{key}</strong> · {source.note}
                      {source.citation?.startsWith("https://") && (
                        <a href={source.citation} target="_blank" rel="noreferrer">
                          FAO ↗
                        </a>
                      )}
                    </p>
                  ))}
              </div>
            </details>
          </article>
        ))}
      </div>
      <section className="rotation-panel">
        <h2>{t("rotations")}</h2>
        <p className="muted">{t("rotationsHint")}</p>
        {rotations.map((rotation) => (
          <div className="rotation-row" key={rotation.id}>
            <div>
              <strong>{rotation.name}</strong>
              <span className="badge amber">{t("experimental")}</span>
            </div>
            <p>
              {rotation.sequence
                .map((code) =>
                  cropName(
                    crops.find((c) => c.code === code),
                    language,
                  ),
                )
                .join(" → ")}
            </p>
          </div>
        ))}
      </section>
    </div>
  );
}
