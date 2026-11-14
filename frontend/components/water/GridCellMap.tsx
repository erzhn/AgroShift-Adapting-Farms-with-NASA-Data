"use client";

// Карта ячеек сетки NASA POWER (раздел 6.3 ТЗ, «честность разрешения»): климат рисуется
// как ячейка ~55 × 50 км, а не как «данные вашего поля».
// Ячейки и точки — векторные, поэтому видны и без сети; подложка OSM — только при наличии.

import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { SnapshotInfo } from "../../lib/api/water";
import { type Lang, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  snapshots: SnapshotInfo[];
  lang: Lang;
}

export default function GridCellMap({ snapshots, lang }: Props) {
  const t = strings(lang);
  const ref = useRef<HTMLDivElement>(null);
  const [noBasemap, setNoBasemap] = useState(false);

  useEffect(() => {
    if (!ref.current || !snapshots.length) return;
    const bounds = new maplibregl.LngLatBounds();
    for (const s of snapshots) {
      bounds.extend([s.cell.bbox[0], s.cell.bbox[1]]);
      bounds.extend([s.cell.bbox[2], s.cell.bbox[3]]);
    }

    const map = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#e9ebe4" } },
          { id: "osm", type: "raster", source: "osm" },
        ],
      },
      bounds,
      fitBoundsOptions: { padding: 36 },
      cooperativeGestures: true,
      locale: {
        "CooperativeGesturesHandler.WindowsHelpText": t.mapHelp,
        "CooperativeGesturesHandler.MacHelpText": t.mapHelp,
        "CooperativeGesturesHandler.MobileHelpText": t.mapHelpMobile,
      },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("error", () => setNoBasemap(true));

    map.on("load", () => {
      map.addSource("cells", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: snapshots.map((s) => {
            const [w, south, e, n] = s.cell.bbox;
            return {
              type: "Feature" as const,
              properties: { code: s.code },
              geometry: {
                type: "Polygon" as const,
                coordinates: [[[w, south], [e, south], [e, n], [w, n], [w, south]]],
              },
            };
          }),
        },
      });
      map.addLayer({ id: "cells-fill", type: "fill", source: "cells",
                     paint: { "fill-color": "#2a78d6", "fill-opacity": 0.1 } });
      map.addLayer({ id: "cells-line", type: "line", source: "cells",
                     paint: { "line-color": "#1c5cab", "line-width": 2 } });
    });

    const markers: maplibregl.Marker[] = [];
    for (const s of snapshots) {
      const point = document.createElement("div");
      point.className = css.mapPoint;
      markers.push(new maplibregl.Marker({ element: point }).setLngLat([s.lon, s.lat])
        .addTo(map));

      const label = document.createElement("div");
      label.className = css.mapLabel;
      label.textContent = s.point_name ?? s.code;
      markers.push(new maplibregl.Marker({ element: label, anchor: "bottom", offset: [0, -10] })
        .setLngLat([s.lon, s.lat]).addTo(map));

      const cellLabel = document.createElement("div");
      cellLabel.className = css.mapLabel;
      cellLabel.textContent = `0,5° × 0,625° · ${Math.round(s.cell.cell_elevation_m)} ${t.m}`;
      markers.push(new maplibregl.Marker({ element: cellLabel, anchor: "top-left",
                                           offset: [6, 6] })
        .setLngLat([s.cell.bbox[0], s.cell.bbox[3]]).addTo(map));
    }

    return () => {
      markers.forEach((m) => m.remove());
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots, lang]);

  return (
    <>
      <div ref={ref} className={css.map} role="img" aria-label={t.gridTitle} />
      {noBasemap && <p className={css.note}>{t.mapFallback}</p>}
    </>
  );
}
