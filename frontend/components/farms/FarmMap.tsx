"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import type { FeatureCollection, Geometry } from "geojson";
import type { Crop, Field, Language } from "@/lib/api/farms";
import { colors, cropName, seasonFor } from "@/lib/farms";
import type { Translate } from "@/lib/i18n";
import Icon from "./Icon";

export default function FarmMap({
  fields,
  crops,
  year,
  selected,
  onSelect,
  t,
  language,
}: {
  fields: Field[];
  crops: Crop[];
  year: number;
  selected: string | null;
  onSelect: (id: string) => void;
  t: Translate;
  language: Language;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;
  const markers = useRef<maplibregl.Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tileError, setTileError] = useState(false);
  const data = useMemo<FeatureCollection<Geometry>>(
    () => ({
      type: "FeatureCollection",
      features: fields.flatMap((f) => {
        const geometry = f.geometry || f.location;
        if (!geometry) return [];
        const crop = crops.find((c) => c.id === seasonFor(f, year)?.crop_id);
        return [
          {
            type: "Feature" as const,
            id: f.id,
            geometry,
            properties: {
              id: f.id,
              color: colors[crop?.code || ""] || "#83918c",
              selected: f.id === selected,
            },
          },
        ];
      }),
    }),
    [fields, crops, year, selected],
  );
  function fit() {
    const current = map.current;
    if (!current || !fields.length) return;
    const bounds = new maplibregl.LngLatBounds();
    for (const field of fields) {
      if (field.geometry)
        for (const point of field.geometry.coordinates[0]) bounds.extend([point[0], point[1]]);
      else if (field.location)
        bounds.extend([field.location.coordinates[0], field.location.coordinates[1]]);
    }
    if (!bounds.isEmpty()) current.fitBounds(bounds, { padding: 65, maxZoom: 16, duration: 500 });
  }
  const fitRef = useRef(fit);
  fitRef.current = fit;
  useEffect(() => {
    if (!container.current) return;
    let current: maplibregl.Map;
    try {
      current = new maplibregl.Map({
        container: container.current,
        center: [74.302, 42.86],
        zoom: 14,
        attributionControl: false,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution:
                '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#e9eddf" } },
            {
              id: "basemap",
              type: "raster",
              source: "osm",
              paint: { "raster-saturation": -0.7, "raster-opacity": 0.55 },
            },
          ],
        },
      });
      map.current = current;
      current.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      current.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      current.on("error", (e) => {
        if ((e as { sourceId?: string }).sourceId === "osm") setTileError(true);
      });
      current.on("load", () => {
        current.addSource("fields", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        current.addLayer({
          id: "field-fill",
          type: "fill",
          source: "fields",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "fill-color": ["get", "color"],
            "fill-opacity": ["case", ["get", "selected"], 0.6, 0.35],
          },
        });
        current.addLayer({
          id: "field-outline",
          type: "line",
          source: "fields",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "line-color": ["get", "color"],
            "line-width": ["case", ["get", "selected"], 4, 2],
          },
        });
        current.addLayer({
          id: "field-point",
          type: "circle",
          source: "fields",
          filter: ["==", ["geometry-type"], "Point"],
          paint: {
            "circle-color": ["get", "color"],
            "circle-radius": 9,
            "circle-stroke-width": 3,
            "circle-stroke-color": "#fff",
          },
        });
        for (const layer of ["field-fill", "field-point"]) {
          current.on("click", layer, (e) => {
            const id = e.features?.[0]?.properties?.id;
            if (id) select.current(id);
          });
          current.on("mouseenter", layer, () => {
            current.getCanvas().style.cursor = "pointer";
          });
          current.on("mouseleave", layer, () => {
            current.getCanvas().style.cursor = "";
          });
        }
        setReady(true);
      });
    } catch {
      setFailed(true);
    }
    const observer = new ResizeObserver(() => map.current?.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("fields") as GeoJSONSource)?.setData(data);
    markers.current.forEach((m) => m.remove());
    markers.current = fields.flatMap((field) => {
      const location = field.location?.coordinates || field.geometry?.coordinates[0][0];
      if (!location) return [];
      const crop = crops.find((c) => c.id === seasonFor(field, year)?.crop_id);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `map-label ${field.id === selected ? "active" : ""}`;
      button.textContent = `${field.name} · ${cropName(crop, language)}`;
      button.setAttribute("aria-label", field.name);
      button.setAttribute("aria-pressed", String(field.id === selected));
      button.addEventListener("click", () => select.current(field.id));
      return [
        new maplibregl.Marker({ element: button, anchor: "bottom", offset: [0, -13] })
          .setLngLat([location[0], location[1]])
          .addTo(map.current!),
      ];
    });
  }, [data, ready, fields, crops, year, selected, language]);
  const boundsKey = fields
    .map((f) => `${f.id}:${JSON.stringify(f.geometry || f.location)}`)
    .join("|");
  useEffect(() => {
    if (ready) fitRef.current();
  }, [ready, boundsKey]);
  return (
    <div className="map-frame">
      <div className="map-canvas" ref={container} role="region" aria-label={t("map")} />
      <div className="map-tag">
        <span className="live-dot" />
        {t("mapAttribution")}
      </div>
      {failed && (
        <div className="map-fallback">
          <Icon name="map" size={40} />
          <p>{t("mapUnavailable")}</p>
        </div>
      )}
      {tileError && <p className="map-warning">{t("tilesUnavailable")}</p>}
      <button type="button" className="map-fit icon-button" onClick={fit} aria-label={t("fitMap")}>
        <Icon name="focus" />
      </button>
      <div className="map-legend">
        {crops
          .filter((c) => fields.some((f) => seasonFor(f, year)?.crop_id === c.id))
          .map((c) => (
            <span key={c.id}>
              <i style={{ background: colors[c.code] }} />
              {cropName(c, language)}
            </span>
          ))}
      </div>
    </div>
  );
}
