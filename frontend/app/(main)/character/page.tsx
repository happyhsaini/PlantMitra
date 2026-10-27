"use client";

import { FormEvent, useMemo, useState } from "react";
import { CHARACTER_PHOTOS, CharacterAvatar } from "@/components/CharacterAvatar";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { useAuth } from "@/components/AuthProvider";
import { api, setSession, type Character } from "@/lib/api";

const PRESETS: Array<{ id: Character["preset"]; title: string; blurb: string; accessory: Character["accessory"] }> = [
  { id: "leaf_spirit", title: "Leaf spirit", blurb: "Gentle reminders from the garden.", accessory: "leaf_crown" },
  { id: "gardener", title: "Gardener", blurb: "Practical watering and pruning tips.", accessory: "hat" },
  { id: "scientist", title: "Scientist", blurb: "Thoughtful about confidence scores.", accessory: "glasses" },
  { id: "forest_guide", title: "Forest guide", blurb: "Notices habitat and the seasons.", accessory: "lantern" },
];

export default function CharacterPage() {
  const { user, setUser } = useAuth();
  const initial = user?.character;
  const [preset, setPreset] = useState<Character["preset"]>(initial?.preset || "leaf_spirit");
  const [name, setName] = useState(initial?.name || "Mitra");
  const [primary, setPrimary] = useState(initial?.primary_color || "#2F7D4A");
  const [secondary, setSecondary] = useState(initial?.secondary_color || "#F4F1E6");
  const [accessory, setAccessory] = useState<Character["accessory"]>(initial?.accessory || "leaf_crown");
  const [greeting, setGreeting] = useState(initial?.greeting || "Namaste! Let's care for a plant today.");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const preview = useMemo(
    () => ({ preset, name, primary_color: primary, secondary_color: secondary, accessory, greeting }),
    [preset, name, primary, secondary, accessory, greeting],
  );

  if (!user) return null;

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.updateMe({ character: preview });
      const token = localStorage.getItem("plantmitra_token");
      if (token) setSession(token, updated);
      setUser(updated);
      setMessage("Character saved. They will greet you on the dashboard.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="character-page">
      <header className="character-heading">
        <div><span className="character-eyebrow"><i /> YOUR GARDEN COMPANION</span><h1>Meet your plant guide</h1><p>Give your companion a look and voice that feels like yours.</p></div>
        <span className="character-heading-mark" aria-hidden="true">✿</span>
      </header>

      <section className="character-stage" aria-label="Live character preview">
        <div className="character-preview-copy"><span>LIVE PREVIEW</span><h2>{name.trim() || "Your companion"}</h2><p>{greeting || "A little hello from the garden."}</p></div>
        <div className="character-avatar-stage"><CharacterAvatar character={preview} size={124} speaking /></div>
        <span className="stage-caption">Your companion will appear around PlantMitra</span>
      </section>

      <section className="character-presets" aria-labelledby="preset-title">
        <div className="character-section-heading"><div><h2 id="preset-title">Choose a starting style</h2><p>You can personalize every detail next.</p></div><span>01 / 02</span></div>
        <div className="character-preset-grid">
        {PRESETS.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => {
              setPreset(item.id);
              setAccessory(item.accessory);
            }}
            aria-pressed={preset === item.id}
            className={`character-preset ${preset === item.id ? "is-selected" : ""}`}
          >
            <img className="preset-photo" src={CHARACTER_PHOTOS[item.id].src} alt={CHARACTER_PHOTOS[item.id].alt} /><span className="preset-copy"><strong>{item.title}</strong><small>{item.blurb}</small></span><span className="preset-check" aria-hidden="true">{preset === item.id ? "✓" : ""}</span>
          </button>
        ))}
        </div>
      </section>

      <form onSubmit={onSave} className="character-form">
        <div className="character-section-heading"><div><h2>Make it yours</h2><p>Choose colors, a little accessory, and their greeting.</p></div><span>02 / 02</span></div>
        <label className="character-field character-name-field">
          Character name
          <input maxLength={24} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <div className="character-color-grid">
          <label className="character-field color-field">
            Primary color
            <span className="color-input-wrap"><input type="color" value={primary} onChange={(e) => setPrimary(e.target.value)} /><code>{primary.toUpperCase()}</code></span>
          </label>
          <label className="character-field color-field">
            Secondary color
            <span className="color-input-wrap"><input type="color" value={secondary} onChange={(e) => setSecondary(e.target.value)} /><code>{secondary.toUpperCase()}</code></span>
          </label>
        </div>
        <label className="character-field">
          Accessory
          <select
            value={accessory}
            onChange={(e) => {
              setAccessory(e.target.value as Character["accessory"]);
              setPreset("custom");
            }}
          >
            <option value="leaf_crown">Leaf crown</option>
            <option value="hat">Hat</option>
            <option value="glasses">Glasses</option>
            <option value="basket">Basket</option>
            <option value="lantern">Lantern</option>
            <option value="none">None</option>
          </select>
        </label>
        <label className="character-field">
          Greeting
          <input maxLength={100} value={greeting} onChange={(e) => setGreeting(e.target.value)} />
        </label>
        <div className="character-form-footer">{message ? <p className={message.startsWith("Character saved") ? "character-message success" : "character-message"} role="status">{message}</p> : <span>Your design saves to your account.</span>}
        <button disabled={busy || !name.trim()} className="character-save-button">
          {busy ? "Saving your companion…" : "Save companion"}<span aria-hidden="true">→</span>
        </button>
        </div>
      </form>
      <div className="character-disclaimer"><DisclaimerBanner compact /></div>
    </main>
  );
}
