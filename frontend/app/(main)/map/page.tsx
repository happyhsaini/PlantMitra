"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { readObservations, type PlantObservation } from "@/lib/observations";

const HOME = { latitude: 23.00261227, longitude: 77.62602107 };
const FEATURED_FLORA = [
  { place: "India", name: "Sacred lotus", scientific: "Nelumbo nucifera", latitude: 23.0026, longitude: 77.6260, image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/69/Indian_Lotus_%28Nelumbo_nucifera%29_flower.jpg/960px-Indian_Lotus_%28Nelumbo_nucifera%29_flower.jpg", credit: "Dr. Chinchu C. · CC BY 4.0", source: "https://commons.wikimedia.org/wiki/File:Indian_Lotus_(Nelumbo_nucifera)_flower.jpg" },
  { place: "Japan", name: "Japanese cherry", scientific: "Prunus serrulata", latitude: 35.6762, longitude: 139.6503, image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/60/.00_3019_Japanische_Bl%C3%BCtenkirsche_%28Prunus_serrulata%29.jpg/960px-.00_3019_Japanische_Bl%C3%BCtenkirsche_%28Prunus_serrulata%29.jpg", credit: "W. Bulach · CC BY-SA 4.0", source: "https://commons.wikimedia.org/wiki/File:.00_3019_Japanische_Bl%C3%BCtenkirsche_(Prunus_serrulata).jpg" },
  { place: "South Africa", name: "King protea", scientific: "Protea cynaroides", latitude: -33.9249, longitude: 18.4241, image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1a/Protea_cynaroides_flower.jpg/960px-Protea_cynaroides_flower.jpg", credit: "Da Legend · Public domain", source: "https://commons.wikimedia.org/wiki/File:Protea_cynaroides_flower.jpg" },
  { place: "Netherlands", name: "Tulip", scientific: "Tulipa 'Red Foxtrot'", latitude: 52.2708, longitude: 4.5476, image: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/Tulip_Red_Foxtrot.jpg/960px-Tulip_Red_Foxtrot.jpg", credit: "Netha Hussain · CC0", source: "https://commons.wikimedia.org/wiki/File:Tulip_Red_Foxtrot.jpg" },
  { place: "United States", name: "Common sunflower", scientific: "Helianthus annuus", latitude: 46.8772, longitude: -96.7898, image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/eb/Sunflowers_helianthus_annuus.jpg/960px-Sunflowers_helianthus_annuus.jpg", credit: "Bruce Fritz / USDA · Public domain", source: "https://commons.wikimedia.org/wiki/File:Sunflowers_helianthus_annuus.jpg" },
];

type MapPosition = { lat: number; lng: number };
type GoogleMapInstance = {
  setCenter: (position: MapPosition) => void;
  setZoom: (zoom: number) => void;
  setMapTypeId: (mapType: string) => void;
  panTo: (position: MapPosition) => void;
};
type GoogleMarker = {
  setMap: (map: GoogleMapInstance | null) => void;
  addListener: (event: string, callback: () => void) => void;
};
type GoogleMapsApi = {
  maps: {
    Map: new (element: HTMLElement, options: Record<string, unknown>) => GoogleMapInstance;
    Marker: new (options: Record<string, unknown>) => GoogleMarker;
    InfoWindow: new (options: { content: string }) => { open: (options: { map: GoogleMapInstance; anchor: GoogleMarker }) => void };
    MapTypeId: { ROADMAP: string; SATELLITE: string };
    SymbolPath: { CIRCLE: string };
  };
};
type MapsWindow = Window & { google?: GoogleMapsApi; plantMitraMapsPromise?: Promise<GoogleMapsApi> };

function loadGoogleMaps(key: string) {
  const appWindow = window as MapsWindow;
  if (appWindow.google?.maps) return Promise.resolve(appWindow.google);
  if (appWindow.plantMitraMapsPromise) return appWindow.plantMitraMapsPromise;

  appWindow.plantMitraMapsPromise = new Promise<GoogleMapsApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&language=en&region=US`;
    script.async = true;
    script.dataset.plantmitraMaps = "true";
    script.onload = () => appWindow.google?.maps ? resolve(appWindow.google) : reject(new Error("Google Maps loaded without its map library."));
    script.onerror = () => reject(new Error("Google Maps could not load. Check that Maps JavaScript API is enabled for this key."));
    document.head.appendChild(script);
  });
  return appWindow.plantMitraMapsPromise;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character] || character);
}

function earthUrl(coordinates: Pick<NonNullable<PlantObservation["coordinates"]>, "latitude" | "longitude">) {
  return `https://earth.google.com/web/@${coordinates.latitude},${coordinates.longitude},0a,3500d,35y,0h,0t,0r`;
}

function formatDate(timestamp: number, fallback: string) {
  return timestamp ? new Date(timestamp).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : fallback;
}

export default function MapPage() {
  const { user } = useAuth();
  const mapElement = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<GoogleMapInstance | null>(null);
  const markers = useRef<GoogleMarker[]>([]);
  const myLocationMarker = useRef<GoogleMarker | null>(null);
  const [observations, setObservations] = useState<PlantObservation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [featuredPlace, setFeaturedPlace] = useState<(typeof FEATURED_FLORA)[number] | null>(null);
  const [mapType, setMapType] = useState<"roadmap" | "satellite">("roadmap");
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState("");
  const [locationMessage, setLocationMessage] = useState("");

  const selected = observations.find((item) => item.id === selectedId) || null;
  const center = selected?.coordinates || (featuredPlace ? { latitude: featuredPlace.latitude, longitude: featuredPlace.longitude } : HOME);
  const mapped = useMemo(() => observations.filter((item) => item.coordinates), [observations]);
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_EMBED_API_KEY || "";

  useEffect(() => {
    if (user) setObservations(readObservations(user.id));
  }, [user]);

  useEffect(() => {
    if (!apiKey) {
      setMapError("Add a Google Maps API key to frontend/.env.local, then restart the app.");
      return;
    }
    let active = true;
    loadGoogleMaps(apiKey).then((api) => {
      if (!active || !mapElement.current) return;
      mapInstance.current = new api.maps.Map(mapElement.current, {
        center: { lat: HOME.latitude, lng: HOME.longitude },
        zoom: 5,
        mapTypeId: api.maps.MapTypeId.ROADMAP,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        clickableIcons: false,
      });
      setMapReady(true);
      setMapError("");
    }).catch((error: unknown) => {
      if (active) setMapError(error instanceof Error ? error.message : "Google Maps could not load.");
    });
    return () => { active = false; };
  }, [apiKey]);

  useEffect(() => {
    if (!mapReady || !mapInstance.current) return;
    mapInstance.current.setCenter({ lat: center.latitude, lng: center.longitude });
    mapInstance.current.setZoom(selected ? 15 : featuredPlace ? 6 : 5);
  }, [center.latitude, center.longitude, featuredPlace, mapReady, selected]);

  useEffect(() => {
    const appWindow = window as MapsWindow;
    const api = appWindow.google;
    const map = mapInstance.current;
    if (!mapReady || !api?.maps || !map) return;
    markers.current.forEach((marker) => marker.setMap(null));
    markers.current = mapped.map((plant) => {
      const marker = new api.maps.Marker({
        map,
        position: { lat: plant.coordinates!.latitude, lng: plant.coordinates!.longitude },
        title: `${plant.name} · ${plant.scientific}`,
        label: { text: plant.name, color: "#173d28", fontSize: "12px", fontWeight: "600" },
        icon: { path: api.maps.SymbolPath.CIRCLE, scale: 9, fillColor: "#79a93e", fillOpacity: 1, strokeColor: "#ffffff", strokeWeight: 3 },
      });
      marker.addListener("click", () => {
        setSelectedId(plant.id);
        setFeaturedPlace(null);
        const image = plant.image ? `<img class="plant-map-popup-image" src="${escapeHtml(plant.image)}" alt="${escapeHtml(plant.name)}">` : "";
        const content = `<article class="plant-map-popup">${image}<strong>🌿 ${escapeHtml(plant.name)}</strong><em>${escapeHtml(plant.scientific)}</em><span>📍 ${escapeHtml(plant.location || "Location not added")}</span><span>📅 ${escapeHtml(formatDate(plant.createdAt, plant.date))}</span><span>👤 ${escapeHtml(user?.display_name || "You")}</span></article>`;
        new api.maps.InfoWindow({ content }).open({ map, anchor: marker });
      });
      return marker;
    });
    return () => markers.current.forEach((marker) => marker.setMap(null));
  }, [mapReady, mapped, user?.display_name]);

  useEffect(() => {
    const api = (window as MapsWindow).google;
    if (mapReady && mapInstance.current && api?.maps) {
      mapInstance.current.setMapTypeId(mapType === "satellite" ? api.maps.MapTypeId.SATELLITE : api.maps.MapTypeId.ROADMAP);
    }
  }, [mapReady, mapType]);

  const useMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setLocationMessage("Location is not available in this browser.");
      return;
    }
    setLocationMessage("Finding your location…");
    navigator.geolocation.getCurrentPosition((position) => {
      const api = (window as MapsWindow).google;
      const map = mapInstance.current;
      if (!api?.maps || !map) return;
      const coords = { lat: position.coords.latitude, lng: position.coords.longitude };
      map.panTo(coords);
      map.setZoom(15);
      myLocationMarker.current?.setMap(null);
      myLocationMarker.current = new api.maps.Marker({ map, position: coords, title: "My location", zIndex: 1000, icon: { path: api.maps.SymbolPath.CIRCLE, scale: 8, fillColor: "#3478d4", fillOpacity: 1, strokeColor: "#ffffff", strokeWeight: 3 } });
      setLocationMessage(`Your location · ±${Math.round(position.coords.accuracy)} m accuracy`);
    }, () => setLocationMessage("Location permission was not granted."), { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
  }, []);

  return (
    <div className="plant-map-page">
      <header className="plant-map-heading">
        <div><span className="eyebrow"><span className="eyebrow-dot" /> FIELD MAP</span><h1>Plant locations</h1><p>Explore saved plant photos at the places they were observed.</p></div>
        <a className="earth-link" href={earthUrl(center)} target="_blank" rel="noreferrer">◎ Open in Google Earth ↗</a>
      </header>

      <section className="plant-map-layout" aria-label="Map and geotagged plant observations">
        <div className="plant-map-frame">
          <div ref={mapElement} className="plant-google-map" aria-label="Interactive map of plant observations" />
          <div className="map-controls">
            <div className="map-type-switch" role="group" aria-label="Map type">
              <button type="button" aria-pressed={mapType === "roadmap"} onClick={() => setMapType("roadmap")}>Roadmap</button>
              <button type="button" aria-pressed={mapType === "satellite"} onClick={() => setMapType("satellite")}>Satellite</button>
            </div>
            <button type="button" className="my-location-button" onClick={useMyLocation} disabled={!mapReady}>◎ My location</button>
          </div>
          {mapError && <div className="map-api-notice" role="status"><strong>Google Maps needs setup</strong><span>{mapError} Enable <b>Maps JavaScript API</b> for this key in the Google Cloud project, then refresh.</span><a href="https://console.cloud.google.com/google/maps-apis/api-list" target="_blank" rel="noreferrer">Open Google Cloud API Library ↗</a></div>}
          {!mapError && !mapReady && <div className="map-loading" role="status">Loading map…</div>}
          {locationMessage && <div className="map-location-message" role="status">{locationMessage}</div>}
        </div>
        <aside className="map-observation-panel"><div className="map-panel-heading"><div><h2>Plant observations</h2><span>{mapped.length} GPS-tagged {mapped.length === 1 ? "plant" : "plants"}</span></div><span className="map-count">{mapped.length}</span></div>
          {selected ? <div className="map-selected-photo"><img src={selected.image} alt={selected.name} /><div><strong>{selected.name}</strong><em>{selected.scientific}</em><span>⌖ {selected.location}</span><small>{selected.coordinates!.latitude.toFixed(5)}, {selected.coordinates!.longitude.toFixed(5)}</small><small>{formatDate(selected.createdAt, selected.date)}</small><a href={earthUrl(selected.coordinates!)} target="_blank" rel="noreferrer">Open this place in Earth ↗</a></div></div> : <div className="map-empty"><span aria-hidden="true">⌖</span><p>No GPS-tagged plants yet</p><small>Save a photo with <b>Use current GPS</b> and identified plants will appear as map markers.</small><a href="/home">Add a plant photo</a></div>}
          {mapped.length > 1 && <div className="map-photo-list" aria-label="Choose a plant observation">{mapped.map((item) => <button type="button" key={item.id} className={item.id === selected?.id ? "selected" : ""} onClick={() => { setSelectedId(item.id); setFeaturedPlace(null); }}><img src={item.image} alt="" /><span><strong>{item.name}</strong><small>{item.location}</small></span><span className="photo-pin" aria-hidden="true">⌖</span></button>)}</div>}
        </aside>
      </section>
      <section className="featured-flora-section" aria-labelledby="featured-flora-title"><div className="featured-flora-heading"><div><span className="eyebrow"><span className="eyebrow-dot" /> PLANTS AROUND THE WORLD</span><h2 id="featured-flora-title">Famous flowers by place</h2><p>Select a place to explore it on the map.</p></div><span className="featured-flora-current">Showing {featuredPlace?.place || selected?.location || "Bhopal, India"}</span></div><div className="featured-flora-grid">{FEATURED_FLORA.map((plant) => <article key={plant.place} className={`featured-flora-card ${featuredPlace?.place === plant.place ? "active" : ""}`}><button type="button" className="featured-flora-select" onClick={() => { setFeaturedPlace(plant); setSelectedId(null); }}><img src={plant.image} alt={`${plant.name} in ${plant.place}`} loading="lazy" /><span className="featured-flora-content"><small>{plant.place}</small><strong>{plant.name}</strong><em>{plant.scientific}</em></span></button><a className="flora-credit" href={plant.source} target="_blank" rel="noreferrer">Photo: {plant.credit}</a></article>)}</div></section>
      <p className="plant-map-note">Map markers use plant observations saved in this browser account. GPS location is only attached when you choose it during photo upload.</p>
    </div>
  );
}
