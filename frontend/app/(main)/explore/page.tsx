"use client";

import { useMemo, useState } from "react";

type Plant = { common: string; scientific: string; genus: string; family: string; region: string[]; photo: string };
type View = "Families" | "Genera" | "Species";
type Region = "All regions" | "Indian subcontinent" | "Asia" | "Africa" | "Europe" | "Americas";
type UserCoordinates = { latitude: number; longitude: number; accuracy: number };

const PLANTS: Plant[] = [
  { common: "Neem", scientific: "Azadirachta indica", genus: "Azadirachta", family: "Meliaceae", region: ["Indian subcontinent", "Asia", "Africa"], photo: "Neem Tree (Azadirachta indica).jpg" },
  { common: "Tulsi", scientific: "Ocimum tenuiflorum", genus: "Ocimum", family: "Lamiaceae", region: ["Indian subcontinent", "Asia"], photo: "Ocimum tenuiflorum.jpg" },
  { common: "Aloe vera", scientific: "Aloe vera", genus: "Aloe", family: "Asphodelaceae", region: ["Africa", "Asia", "Americas"], photo: "Aloe Vera.jpg" },
  { common: "Ashwagandha", scientific: "Withania somnifera", genus: "Withania", family: "Solanaceae", region: ["Indian subcontinent", "Asia", "Africa"], photo: "Withania somnifera (L.) Dunal (21776964472).jpg" },
  { common: "Amla", scientific: "Phyllanthus emblica", genus: "Phyllanthus", family: "Phyllanthaceae", region: ["Indian subcontinent", "Asia"], photo: "Phyllanthus emblica (4449651839).jpg" },
  { common: "Moringa", scientific: "Moringa oleifera", genus: "Moringa", family: "Moringaceae", region: ["Indian subcontinent", "Asia", "Africa"], photo: "Starr 080609-7913 Moringa oleifera.jpg" },
  { common: "Brahmi", scientific: "Bacopa monnieri", genus: "Bacopa", family: "Plantaginaceae", region: ["Indian subcontinent", "Asia", "Africa", "Americas"], photo: "Bacopa monnieri (L.) Wettst. (2465019988).jpg" },
  { common: "Gotu kola", scientific: "Centella asiatica", genus: "Centella", family: "Apiaceae", region: ["Indian subcontinent", "Asia", "Africa"], photo: "CentellaAsiatica.jpg" },
  { common: "Mint", scientific: "Mentha species", genus: "Mentha", family: "Lamiaceae", region: ["Indian subcontinent", "Asia", "Africa", "Europe", "Americas"], photo: "Mentha spicata sl22.jpg" },
  { common: "Turmeric", scientific: "Curcuma longa", genus: "Curcuma", family: "Zingiberaceae", region: ["Indian subcontinent", "Asia", "Africa"], photo: "Curcuma longa flower.jpg" },
];

function commonsFileUrl(file: string) {
  return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=480`;
}

function commonsPageUrl(file: string) {
  return `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(file).replace(/%20/g, "_")}`;
}

const REGIONS: Region[] = ["All regions", "Indian subcontinent", "Asia", "Africa", "Europe", "Americas"];

function regionFromCoordinates(latitude: number, longitude: number): Region {
  if (latitude >= 5 && latitude <= 37 && longitude >= 60 && longitude <= 100) return "Indian subcontinent";
  if (latitude >= -12 && latitude <= 55 && longitude >= 60 && longitude <= 150) return "Asia";
  if (latitude >= -36 && latitude <= 38 && longitude >= -20 && longitude <= 52) return "Africa";
  if (latitude >= 35 && latitude <= 72 && longitude >= -12 && longitude <= 45) return "Europe";
  if (longitude <= -30 || longitude >= 160) return "Americas";
  return "All regions";
}

export default function ExplorePage() {
  const [view, setView] = useState<View>("Species");
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("All families");
  const [genus, setGenus] = useState("All genera");
  const [region, setRegion] = useState<Region>("All regions");
  const [sort, setSort] = useState("A to Z");
  const [filterOpen, setFilterOpen] = useState(false);
  const [regionOpen, setRegionOpen] = useState(false);
  const [regionTab, setRegionTab] = useState<"All" | "Near me">("All");
  const [geoMessage, setGeoMessage] = useState("");
  const [coordinates, setCoordinates] = useState<UserCoordinates | null>(null);

  const families = useMemo(() => Array.from(new Set(PLANTS.map((plant) => plant.family))).sort(), []);
  const genera = useMemo(() => Array.from(new Set(PLANTS.map((plant) => plant.genus))).sort(), []);
  const filteredPlants = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return PLANTS.filter((plant) => {
      const matchesQuery = !term || `${plant.common} ${plant.scientific} ${plant.genus} ${plant.family}`.toLocaleLowerCase().includes(term);
      return matchesQuery && (family === "All families" || plant.family === family) && (genus === "All genera" || plant.genus === genus) && (region === "All regions" || plant.region.includes(region));
    }).sort((a, b) => sort === "Z to A" ? b.common.localeCompare(a.common) : sort === "Scientific name" ? a.scientific.localeCompare(b.scientific) : a.common.localeCompare(b.common));
  }, [family, genus, query, region, sort]);

  const activeFilters = [family !== "All families", genus !== "All genera", region !== "All regions"].filter(Boolean).length;
  const mapUrl = coordinates
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${coordinates.longitude - 0.04}%2C${coordinates.latitude - 0.025}%2C${coordinates.longitude + 0.04}%2C${coordinates.latitude + 0.025}&layer=mapnik&marker=${coordinates.latitude}%2C${coordinates.longitude}`
    : "";

  function clearFilters() {
    setFamily("All families");
    setGenus("All genera");
    setRegion("All regions");
    setQuery("");
  }

  function useLocation() {
    setGeoMessage("");
    if (!navigator.geolocation) {
      setGeoMessage("Location is not available in this browser. Choose a region from All instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const detected = regionFromCoordinates(coords.latitude, coords.longitude);
        setCoordinates({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy });
        if (detected === "All regions") setGeoMessage("Your GPS coordinates are shown on this page. We could not match them to a catalogue region.");
        else {
          setRegion(detected);
          setGeoMessage(`Region filter set to ${detected}. This broad catalogue filter does not represent nearby sightings.`);
        }
      },
      () => setGeoMessage("Location permission was not granted. Choose a region from All instead."),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  const grouped = view === "Families" ? Array.from(new Set(filteredPlants.map((plant) => plant.family))) : view === "Genera" ? Array.from(new Set(filteredPlants.map((plant) => plant.genus))) : [];

  return (
    <div className="explore-page">
      <header className="explore-heading">
        <div><span className="explore-eyebrow"><i /> PLANT LIBRARY</span><h1>Explore medicinal plants</h1><p>Browse a starter reference list by species, genus, or family.</p></div>
        <span className="explore-heading-mark" aria-hidden="true">♧</span>
      </header>

      <section className="explore-search-band" aria-label="Search plant library">
        <label className="explore-search"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search common name, scientific name, genus, or family" aria-label="Search plant library" />{query && <button type="button" onClick={() => setQuery("")} aria-label="Clear search">×</button>}</label>
      </section>

      <nav className="explore-tabs" aria-label="Browse taxonomy">
        {(["Families", "Genera", "Species"] as const).map((item) => <button key={item} type="button" className={view === item ? "active" : ""} onClick={() => setView(item)}>{item}</button>)}
      </nav>

      <section className="explore-toolbar" aria-label="Plant library filters">
        <div className="explore-toolbar-actions">
          <button className={`explore-filter-button ${filterOpen ? "active" : ""}`} type="button" onClick={() => setFilterOpen((open) => !open)} aria-expanded={filterOpen}><span aria-hidden="true">☷</span> Filters{activeFilters > 0 && <b>{activeFilters}</b>}</button>
          <button className="explore-region-button" type="button" onClick={() => { setRegionTab("All"); setRegionOpen(true); }}><span aria-hidden="true">⌖</span> Filter by region</button>
        </div>
        <div className="explore-sort"><span><strong>{filteredPlants.length}</strong> plants</span><label>Sort by<select value={sort} onChange={(event) => setSort(event.target.value)}><option>A to Z</option><option>Z to A</option><option>Scientific name</option></select></label></div>
      </section>

      {filterOpen && <section className="explore-filter-panel" aria-label="Taxonomy filters">
        <label>Family<select value={family} onChange={(event) => setFamily(event.target.value)}><option>All families</option>{families.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Genus<select value={genus} onChange={(event) => setGenus(event.target.value)}><option>All genera</option>{genera.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Region<select value={region} onChange={(event) => setRegion(event.target.value as Region)}>{REGIONS.map((item) => <option key={item}>{item}</option>)}</select></label>
        {activeFilters > 0 && <button type="button" onClick={clearFilters}>Clear filters</button>}
      </section>}

      {region !== "All regions" && <p className="region-context"><span aria-hidden="true">⌖</span> Region: <strong>{region}</strong><button type="button" onClick={() => setRegion("All regions")}>Clear</button></p>}

      {coordinates && <section className="explore-gps-panel" aria-label="Your GPS position on map"><div className="explore-gps-info"><div><span className="gps-live-dot" /><strong>Your GPS position</strong></div><small>Latitude&nbsp; {coordinates.latitude.toFixed(5)}<br />Longitude&nbsp; {coordinates.longitude.toFixed(5)}<br />Accuracy&nbsp; about {Math.round(coordinates.accuracy)} m</small><a href={`https://www.openstreetmap.org/?mlat=${coordinates.latitude}&mlon=${coordinates.longitude}#map=14/${coordinates.latitude}/${coordinates.longitude}`} target="_blank" rel="noreferrer">Open larger map ↗</a><button type="button" onClick={() => setCoordinates(null)}>Hide location</button></div><iframe title="OpenStreetMap showing your current GPS position" loading="lazy" referrerPolicy="no-referrer" src={mapUrl} /></section>}

      {view === "Species" ? <div className="explore-plant-grid">{filteredPlants.map((plant) => <article className="explore-plant-row" key={plant.scientific}><img className="explore-plant-photo" src={commonsFileUrl(plant.photo)} alt={`${plant.common} (${plant.scientific})`} loading="lazy" /><div className="explore-plant-name"><h2>{plant.scientific}</h2><p>{plant.common}</p><a className="explore-photo-source" href={commonsPageUrl(plant.photo)} target="_blank" rel="noreferrer">Photo source: Wikimedia Commons ↗</a></div><div className="explore-plant-taxonomy"><span><small>GENUS</small><i>{plant.genus}</i></span><span><small>FAMILY</small><i>{plant.family}</i></span></div></article>)}</div> : <div className="explore-group-grid">{grouped.map((item) => <button key={item} type="button" className="explore-group-item" onClick={() => { if (view === "Families") setFamily(item); else setGenus(item); setView("Species"); }}><span className="group-leaf-mark" aria-hidden="true">✿</span><strong>{item}</strong><small>{filteredPlants.filter((plant) => view === "Families" ? plant.family === item : plant.genus === item).length} plants</small><span className="group-arrow" aria-hidden="true">→</span></button>)}</div>}

      {filteredPlants.length === 0 && <div className="explore-empty"><span>⌕</span><h2>No plants match these filters</h2><p>Try a different search or clear the selected filters.</p><button type="button" onClick={clearFilters}>Clear filters</button></div>}

      <p className="explore-note">Starter reference list only. This catalogue does not represent live observations or confirmed model classes.</p>

      {regionOpen && <div className="region-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setRegionOpen(false)}><section className="region-modal" role="dialog" aria-modal="true" aria-labelledby="region-dialog-title">
        <header><h2 id="region-dialog-title">Choose a region</h2><button type="button" onClick={() => setRegionOpen(false)} aria-label="Close region selector">×</button></header>
        <div className="region-modal-tabs"><button type="button" className={regionTab === "All" ? "active" : ""} onClick={() => setRegionTab("All")}>All regions</button><button type="button" className={regionTab === "Near me" ? "active" : ""} onClick={() => setRegionTab("Near me")}>Near me</button></div>
        {regionTab === "All" ? <div className="region-choice-grid">{REGIONS.filter((item) => item !== "All regions").map((item) => <button key={item} type="button" className={region === item ? "selected" : ""} onClick={() => { setRegion(item); setRegionOpen(false); }}><span aria-hidden="true">⌖</span><strong>{item}</strong><small>{PLANTS.filter((plant) => plant.region.includes(item)).length} reference plants</small></button>)}</div> : <div className="region-nearby"><span className="nearby-symbol" aria-hidden="true">⌖</span><h3>Use your location</h3><p>Your browser location is used only to choose a broad region. Exact coordinates are not saved, and results are not nearby sightings.</p><button type="button" onClick={useLocation}>Use my location</button>{geoMessage && <small role="status">{geoMessage}</small>}</div>}
        <p className="region-modal-note">Region tags are broad catalogue categories, not verified sightings or exact distribution data.</p>
      </section></div>}
    </div>
  );
}
