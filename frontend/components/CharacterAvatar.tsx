"use client";

type CharacterLite = {
  preset: string;
  name: string;
  primary_color: string;
  secondary_color?: string;
  accessory: string;
};

export const CHARACTER_PHOTOS: Record<string, { src: string; alt: string }> = {
  leaf_spirit: { src: "https://images.unsplash.com/photo-1609937451064-626cfe9fc64d?auto=format&fit=crop&w=520&h=520&q=82", alt: "Close-up of a fresh green leaf" },
  gardener: { src: "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?auto=format&fit=crop&w=520&h=520&q=82", alt: "Hands tending plants in a garden" },
  scientist: { src: "https://images.unsplash.com/photo-1572978577745-245cde7e1da3?auto=format&fit=crop&w=520&h=520&q=82", alt: "Young basil plant growing in a pot" },
  forest_guide: { src: "https://images.unsplash.com/photo-1670839376702-2b40e22a4bb7?auto=format&fit=crop&w=520&h=520&q=82", alt: "Sunlit ferns growing in a forest" },
  custom: { src: "https://images.unsplash.com/photo-1609937451064-626cfe9fc64d?auto=format&fit=crop&w=520&h=520&q=82", alt: "Close-up of a fresh green leaf" },
};

export function CharacterAvatar({
  character,
  size = 72,
  speaking = false,
}: {
  character?: CharacterLite | null;
  size?: number;
  speaking?: boolean;
}) {
  const color = character?.primary_color || "#2F7D4A";
  const photo = CHARACTER_PHOTOS[character?.preset || "leaf_spirit"] || CHARACTER_PHOTOS.leaf_spirit;
  return (
    <div className="character-avatar">
      <div
        className={`character-avatar-photo ${speaking ? "is-speaking" : ""}`}
        style={{
          width: size,
          height: size,
          border: `3px solid ${color}`,
          backgroundColor: character?.secondary_color || "#F4F1E6",
        }}
      >
        <img src={photo.src} alt={photo.alt} />
        {character?.accessory && character.accessory !== "none" ? (
          <span className="character-accessory">
            {character.accessory === "hat"
              ? "🎩"
              : character.accessory === "glasses"
                ? "👓"
                : character.accessory === "basket"
                  ? "🧺"
                  : character.accessory === "lantern"
                    ? "🏮"
                    : "👑"}
          </span>
        ) : null}
      </div>
      <p>{character?.name || "Mitra"}</p>
    </div>
  );
}
