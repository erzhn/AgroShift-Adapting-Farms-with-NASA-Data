"use client";

// Карточка поля: /field/<id>?strategy=<id>&scenario=<id>&lang=ru|en|ky
// До подключения модуля хозяйств работают демо-поля: asan-maize, asan-alfalfa, asan-orchard.

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import FieldWaterCard from "../../../components/water/FieldWaterCard";

function FieldPage() {
  const params = useParams<{ id: string }>();
  const query = useSearchParams();
  return (
    <FieldWaterCard fieldId={decodeURIComponent(params.id)}
                    strategy={query.get("strategy") ?? undefined}
                    scenario={query.get("scenario") ?? undefined} />
  );
}

export default function Page() {
  return (
    <Suspense>
      <FieldPage />
    </Suspense>
  );
}
