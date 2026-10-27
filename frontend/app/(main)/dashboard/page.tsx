"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PLANT_PARTS, readObservations, type PlantObservation } from "@/lib/observations";

type DateFilter = "Any time" | "Today" | "Last 7 days" | "Last 30 days" | "This year";
type SortFilter = "Newest first" | "Oldest first" | "Species A-Z" | "Highest confidence";

const DATE_FILTERS: DateFilter[] = ["Any time", "Today", "Last 7 days", "Last 30 days", "This year"];
const CONFIDENCE_FILTERS = ["Any confidence", "50% and above", "70% and above", "90% and above"];

function dateStart(filter: DateFilter): number {
  const now = new Date();
  if (filter === "Today") return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (filter === "Last 7 days") return now.getTime() - 7 * 24 * 60 * 60 * 1000;
  if (filter === "Last 30 days") return now.getTime() - 30 * 24 * 60 * 60 * 1000;
  if (filter === "This year") return new Date(now.getFullYear(), 0, 1).getTime();
  return 0;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [observations, setObservations] = useState<PlantObservation[]>([]);
  const [search, setSearch] = useState("");
  const [speciesFilter, setSpeciesFilter] = useState("All species");
  const [familyFilter, setFamilyFilter] = useState("All families");
  const [partFilter, setPartFilter] = useState("All plant parts");
  const [dateFilter, setDateFilter] = useState<DateFilter>("Any time");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [locationFilter, setLocationFilter] = useState("All locations");
  const [locationSearch, setLocationSearch] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState(CONFIDENCE_FILTERS[0]);
  const [statusFilter, setStatusFilter] = useState("All results");
  const [sortFilter, setSortFilter] = useState<SortFilter>("Newest first");

  useEffect(() => {
    if (!user) return;
    setObservations(readObservations(user.id));
  }, [user]);

  const species = useMemo(() => Array.from(new Set(observations.filter((item) => item.status === "Identified").map((item) => item.name))).sort(), [observations]);
  const families = useMemo(() => Array.from(new Set(observations.map((item) => item.family).filter((item) => item && item !== "Unknown"))).sort(), [observations]);
  const locations = useMemo(() => Array.from(new Set(observations.map((item) => item.location).filter((item) => item && item !== "Location not added"))).sort(), [observations]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const confidenceFloor = confidenceFilter === "90% and above" ? 90 : confidenceFilter === "70% and above" ? 70 : confidenceFilter === "50% and above" ? 50 : 0;
    const start = dateStart(dateFilter);
    return observations.filter((item) => {
      const matchesTerm = !term || `${item.name} ${item.scientific} ${item.family} ${item.location} ${item.plantPart} ${item.note || ""}`.toLowerCase().includes(term);
      const matchesSpecies = speciesFilter === "All species" || item.name === speciesFilter;
      const matchesFamily = familyFilter === "All families" || item.family === familyFilter;
      const matchesPart = partFilter === "All plant parts" || item.plantPart === partFilter;
      const matchesDate = item.createdAt >= start && (!dateFrom || item.createdAt >= new Date(`${dateFrom}T00:00:00`).getTime()) && (!dateTo || item.createdAt <= new Date(`${dateTo}T23:59:59.999`).getTime());
      const matchesLocation = locationFilter === "All locations" || item.location === locationFilter;
      const matchesLocationSearch = !locationSearch.trim() || item.location.toLowerCase().includes(locationSearch.trim().toLowerCase());
      const matchesConfidence = item.confidence >= confidenceFloor;
      const matchesStatus = statusFilter === "All results" || (statusFilter === "Identified" ? item.status === "Identified" : item.status !== "Identified");
      return matchesTerm && matchesSpecies && matchesFamily && matchesPart && matchesDate && matchesLocation && matchesLocationSearch && matchesConfidence && matchesStatus;
    }).sort((a, b) => sortFilter === "Oldest first" ? a.createdAt - b.createdAt : sortFilter === "Highest confidence" ? b.confidence - a.confidence : sortFilter === "Species A-Z" ? a.name.localeCompare(b.name) : b.createdAt - a.createdAt);
  }, [confidenceFilter, dateFilter, dateFrom, dateTo, familyFilter, locationFilter, locationSearch, observations, partFilter, search, sortFilter, speciesFilter, statusFilter]);

  const identified = observations.filter((item) => item.status === "Identified");
  const stats = [
    { label: "Plants identified", value: identified.length, symbol: "✿", tint: "moss" },
    { label: "Photos collected", value: observations.filter((item) => Boolean(item.image)).length, symbol: "▧", tint: "sage" },
    { label: "Species discovered", value: new Set(identified.map((item) => item.scientific)).size, symbol: "◌", tint: "citrus" },
    { label: "Plant parts recorded", value: new Set(observations.map((item) => item.plantPart)).size, symbol: "⌁", tint: "coral" },
  ];
  const activeFilterCount = [
    search.trim().length > 0,
    speciesFilter !== "All species",
    familyFilter !== "All families",
    partFilter !== "All plant parts",
    dateFilter !== "Any time",
    Boolean(dateFrom || dateTo),
    locationFilter !== "All locations",
    Boolean(locationSearch.trim()),
    confidenceFilter !== "Any confidence",
    statusFilter !== "All results",
  ].filter(Boolean).length;

  function clearFilters() {
    setSearch("");
    setSpeciesFilter("All species");
    setFamilyFilter("All families");
    setPartFilter("All plant parts");
    setDateFilter("Any time");
    setDateFrom("");
    setDateTo("");
    setLocationFilter("All locations");
    setLocationSearch("");
    setConfidenceFilter(CONFIDENCE_FILTERS[0]);
    setStatusFilter("All results");
    setSortFilter("Newest first");
  }

  return (
    <div className="garden-dashboard">
      <header className="garden-heading">
        <div>
          <span className="garden-eyebrow"><span /> PLANTMITRA · YOUR GARDEN</span>
          <h1>{user ? `Welcome back, ${user.display_name.split(" ")[0]}` : "Your garden"}</h1>
          <p>Keep your plant discoveries growing in one place.</p>
        </div>
        <Link className="garden-scan-button" href="/home"><span>＋</span> Scan a plant</Link>
      </header>

      <section className="garden-hero" aria-label="Plant discovery">
        <div className="garden-hero-copy">
          <span>PLANT COLLECTION · FIELD JOURNAL</span>
          <h2>A closer look at<br />the living world.</h2>
          <p>Every observation adds a little more to what we know.</p>
          <Link href="/home">Make an observation <span>→</span></Link>
        </div>
        <img src="https://images.unsplash.com/photo-1701138161189-ef3bba4bf88a?auto=format&fit=crop&w=1400&q=85" alt="Young turmeric leaves growing in a garden" />
        <span className="hero-caption">PHOTO · VASANTH KUMAR / UNSPLASH</span>
      </section>

      <section className="garden-stats" aria-label="Your plant statistics">
        {stats.map((stat) => <article className={`garden-stat ${stat.tint}`} key={stat.label}><span className="garden-stat-symbol">{stat.symbol}</span><div><strong>{stat.value}</strong><span>{stat.label}</span></div></article>)}
      </section>

      <section className="collection-section" aria-labelledby="collection-title">
        <div className="collection-heading">
          <div><span className="garden-eyebrow"><span /> FIELD JOURNAL</span><h2 id="collection-title">Your observations</h2><p>Search and refine your own plant records.</p></div>
          <span className="result-count">{filtered.length} of {observations.length} records</span>
        </div>

        <div className="garden-filters" aria-label="Filter plant observations">
          <label className="garden-search"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, family, part, notes" aria-label="Search plants" /></label>
          <label className="filter-control"><span>Species</span><select value={speciesFilter} onChange={(event) => setSpeciesFilter(event.target.value)}><option>All species</option>{species.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Family</span><select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)}><option>All families</option>{families.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Plant part</span><select value={partFilter} onChange={(event) => setPartFilter(event.target.value)}><option>All plant parts</option>{PLANT_PARTS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Date added</span><select value={dateFilter} onChange={(event) => setDateFilter(event.target.value as DateFilter)}>{DATE_FILTERS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Location</span><select value={locationFilter} onChange={(event) => setLocationFilter(event.target.value)}><option>All locations</option>{locations.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Location contains</span><input type="search" value={locationSearch} onChange={(event) => setLocationSearch(event.target.value)} placeholder="Search any place" /></label>
          <label className="filter-control"><span>From date</span><input type="date" value={dateFrom} max={dateTo || undefined} onChange={(event) => setDateFrom(event.target.value)} /></label>
          <label className="filter-control"><span>To date</span><input type="date" value={dateTo} min={dateFrom || undefined} onChange={(event) => setDateTo(event.target.value)} /></label>
          <label className="filter-control"><span>Confidence</span><select value={confidenceFilter} onChange={(event) => setConfidenceFilter(event.target.value)}>{CONFIDENCE_FILTERS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-control"><span>Result</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option>All results</option><option>Identified</option><option>Needs identification</option></select></label>
          <label className="filter-control sort-control"><span>Sort by</span><select value={sortFilter} onChange={(event) => setSortFilter(event.target.value as SortFilter)}><option>Newest first</option><option>Oldest first</option><option>Species A-Z</option><option>Highest confidence</option></select></label>
          {activeFilterCount > 0 && <button className="clear-filters" onClick={clearFilters}>Clear filters <span>{activeFilterCount}</span></button>}
        </div>

        {filtered.length > 0 ? <div className="garden-observation-grid">{filtered.map((item) => <article className="garden-observation" key={item.id}>
          <div className="garden-observation-photo"><img src={item.image} alt={item.name} /><span className="photo-part">{item.plantPart}</span>{item.status === "Identified" && <span className="photo-confidence">{item.confidence}%</span>}</div>
          <div className="garden-observation-info"><div><h3>{item.name}</h3><p>{item.scientific}</p></div><span className={item.status === "Identified" ? "result-status confirmed" : "result-status pending"}>{item.status === "Identified" ? "Identified" : "Needs ID"}</span></div>
          <div className="garden-observation-meta"><span>⌖ {item.location}</span><time dateTime={new Date(item.createdAt).toISOString()}>{item.date}</time></div>
        </article>)}</div> : <div className="garden-empty"><img src="https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=480&q=80" alt="A young plant growing toward the light" /><div><span className="garden-eyebrow"><span /> {observations.length ? "NO MATCHES" : "A FRESH PAGE"}</span><h3>{observations.length ? "No plants match these filters." : "Your field journal starts here."}</h3><p>{observations.length ? "Adjust a filter or clear them to see your observations." : "Add a plant photo to start building your own botanical collection."}</p><Link href="/home">Scan your first plant <span>→</span></Link></div>{observations.length > 0 && <button className="clear-empty-filters" onClick={clearFilters}>Clear filters</button>}</div>}
      </section>

      <p className="garden-disclaimer">AI plant suggestions may be wrong, even when confidence is high. Do not eat or use a plant medicinally based on an identification alone. Confirm the species with a qualified botanist and consult a healthcare professional before medicinal use.</p>
    </div>
  );
}
