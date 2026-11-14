"use client";

import { useEffect, useRef } from "react";
import {
  Map as MapLibreMap,
  NavigationControl,
  type GeoJSONSource,
} from "maplibre-gl";
import type { FeatureCollection, Geometry, Point } from "geojson";

type CanalGeo = { geometry: Geometry | null };
type FarmGeo = {
  farm_id: string;
  farm_name: string;
  field_id: string;
  field_name: string;
  area_ha: number;
  location: Point | null;
  geometry: Geometry | null;
};

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

export default function CanalMap({ canal, farms }: { canal: CanalGeo | null; farms: FarmGeo[] }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new MapLibreMap({
      container: container.current,
      center: [74.59, 42.87],
      zoom: 10,
      minZoom: 6,
      maxZoom: 17,
      attributionControl: { compact: true },
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
          { id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.35 } },
        ],
      },
    });
    map.current = instance;
    instance.addControl(new NavigationControl({ showCompass: false }), "top-right");
    instance.once("load", () => {
      instance.addSource("canal", { type: "geojson", data: EMPTY });
      instance.addLayer({
        id: "canal-line",
        type: "line",
        source: "canal",
        paint: { "line-color": "#159b85", "line-width": 4, "line-opacity": 0.9 },
      });
      instance.addSource("fields", { type: "geojson", data: EMPTY });
      instance.addLayer({
        id: "field-fill",
        type: "fill",
        source: "fields",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#d2aa58", "fill-opacity": 0.3 },
      });
      instance.addLayer({
        id: "field-outline",
        type: "line",
        source: "fields",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "line-color": "#a37a2e", "line-width": 1.5 },
      });
      instance.addLayer({
        id: "farm-points",
        type: "circle",
        source: "fields",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 6,
          "circle-color": "#197c6d",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#f9f8f3",
        },
      });
    });
    return () => {
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const current = map.current;
    if (!current || !current.isStyleLoaded()) return;
    const canalSource = current.getSource("canal") as GeoJSONSource | undefined;
    const fieldSource = current.getSource("fields") as GeoJSONSource | undefined;
    if (canalSource) {
      const features = canal?.geometry
        ? [{ type: "Feature" as const, properties: {}, geometry: canal.geometry }]
        : [];
      canalSource.setData({ type: "FeatureCollection", features });
    }
    if (fieldSource) {
      const features = farms.flatMap((farm) => {
        const properties = {
          farm_id: farm.farm_id,
          farm_name: farm.farm_name,
          field_name: farm.field_name,
          area_ha: farm.area_ha,
        };
        return [farm.geometry, farm.location]
          .filter((geometry): geometry is Geometry => geometry !== null)
          .map((geometry) => ({ type: "Feature" as const, properties, geometry }));
      });
      fieldSource.setData({ type: "FeatureCollection", features });
    }
  }, [canal, farms]);

  return <div className="map-canvas" ref={container} aria-label="Карта канала и хозяйств" />;
}
