export function DisclaimerBanner({ compact = false }: { compact?: boolean }) {
  return (
    <aside className="disclaimer">
      <p className="font-semibold">Disclaimer</p>
      <p>
        PlantMitra provides AI-assisted plant suggestions and general growing information for learning only.
        Results can be wrong or incomplete, even when confidence is high. Never eat, apply, or use a plant as
        medicine based on an identification alone. Confirm the species with a qualified botanist and consult
        a licensed healthcare professional before medicinal use. Growing tips may not suit your plant or local conditions.
      </p>
      {compact ? null : (
        <p className="mt-1 text-[11px] text-leaf-700">
          AI ki pehchan galat ho sakti hai. Kisi plant ko khane ya dawa ki tarah use karne se pehle experts se tasdeeq karein.
        </p>
      )}
    </aside>
  );
}
