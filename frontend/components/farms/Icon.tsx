import type { CSSProperties } from "react";

const paths = {
  leaf: "M20 4c-8-2-15 2-15 8a6 6 0 0 0 6 6c6 0 10-7 9-14ZM4 21l10-10",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  map: "m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5Zm6-2v16m6-14v16",
  field: "m3 6 17-3 1 14-14 4-4-15Zm1 4 17-3M5 14l16-3M7 21l-3-15m9 13L10 5",
  wallet: "M20 8V5H5a2 2 0 0 0 0 4h16v11H5a2 2 0 0 1-2-2V7m18 6h-5v3h5",
  cow: "M5 8 2 4m17 4 3-4M7 7H4v6h3m10-6h3v6h-3M8 6h8l2 12-4 3h-4l-4-3L8 6Zm2 8v1m4-1v1m-4 3h4",
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M6 18 18 6",
  edit: "m16 3 5 5-12 12H4v-5L16 3Zm-2 2 5 5",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  check: "m5 12 4 4L19 6",
  chevron: "m8 4 8 8-8 8",
  drop: "M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13Z",
  calendar: "M4 5h16v16H4zM8 2v6m8-6v6M4 11h16m-12 4h1m6 0h1",
  info: "M12 11v6m0-10v1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  trash: "M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
  focus: "M3 8V3h5m8 0h5v5m0 8v5h-5M8 21H3v-5M8 12h8m-4-4v8",
  menu: "M4 6h16M4 12h16M4 18h16",
  book: "M12 5C7 2 3 4 3 4v16s4-2 9 1c5-3 9-1 9-1V4s-4-2-9 1Zm0 0v16",
};
export default function Icon({
  name,
  size = 20,
  style,
}: {
  name: keyof typeof paths;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
