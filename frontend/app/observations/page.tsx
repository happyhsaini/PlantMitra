"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { PLANT_PARTS, readObservations, writeObservations, type PlantObservation, type PlantPart } from "@/lib/observations";
import { api, getApiUrl, getToken, type PlantIdentification, type ReferenceResponse } from "@/lib/api";

const filters = ["All observations", "Identified", "Needs identification"];
const PART_STICKERS: Record<PlantPart, string> = {
  Leaf: "🌿",
  Flower: "🌸",
  Fruit: "🍊",
  Bark: "🪵",
  Habit: "🌳",
  Other: "✿",
  Branch: "🌱",
  Seed: "🌰",
  Bud: "🌱",
  "Aerial picture": "⌖",
  Root: "⌖",
  Stem: "🌱",
  Aerial: "⌖",
};

function compressedImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read this image."));
    reader.onload = () => {
      const source = new Image();
      source.onerror = () => reject(new Error("Could not open this image."));
      source.onload = () => {
        const scale = Math.min(1, 1400 / Math.max(source.width, source.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(source.width * scale);
        canvas.height = Math.round(source.height * scale);
        const context = canvas.getContext("2d");
        if (!context) return reject(new Error("Image processing is unavailable in this browser."));
        context.drawImage(source, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.78));
      };
      source.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}

export default function ObservationsPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [observations, setObservations] = useState<PlantObservation[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState(filters[0]);
  const [partFilter, setPartFilter] = useState<PlantPart | "All">("All");
  const [selected, setSelected] = useState<PlantObservation | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [image, setImage] = useState<string | null>(null);
  const [storedImage, setStoredImage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [plantPart, setPlantPart] = useState<PlantPart>("Leaf");
  const [location, setLocation] = useState("");
  const [coordinates, setCoordinates] = useState<PlantObservation["coordinates"]>();
  const [geoMessage, setGeoMessage] = useState("");
  const [oldestFirst, setOldestFirst] = useState(false);
  const [identifyError, setIdentifyError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraVideoRef = useRef<HTMLVideoElement>(null);
  const cameraRequestRef = useRef(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState("");
  const [identification, setIdentification] = useState<PlantIdentification | null>(null);
  const [reference, setReference] = useState<ReferenceResponse["observations"]>([]);
  const [referencesLoading, setReferencesLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    setObservations(readObservations(user.id));
    api.observations().then(async ({ observations: remote }) => {
      const local = readObservations(user.id);
      const cachedById = new Map(local.filter((item) => item.serverBacked).map((item) => [item.id, item]));
      const synced = await Promise.all(remote.map(async (item) => {
        const cached = cachedById.get(item.id);
        if (cached?.image) return { ...item, image: cached.image };
        try {
          const response = await fetch(`${getApiUrl()}${item.image_url}`, { headers: { Authorization: `Bearer ${getToken()}` } });
          if (!response.ok) return item;
          const blob = await response.blob();
          const preview = await compressedImage(new File([blob], `plant-${item.id}`, { type: blob.type || "image/jpeg" }));
          return { ...item, image: preview };
        } catch { return item; }
      }));
      const legacy = local.filter((item) => !item.serverBacked);
      const merged = [...synced, ...legacy];
      setObservations(merged);
      writeObservations(user.id, merged);
    }).catch(() => setNotice("Could not sync with your account. Showing observations saved on this device."));
  }, [user]);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, router, user]);

  useEffect(() => {
    if (!cameraStream) return;
    const video = cameraVideoRef.current;
    if (video) {
      video.srcObject = cameraStream;
      void video.play().catch(() => setCameraError("Camera preview could not start. Check browser camera permission."));
    }
    return () => {
      cameraStream.getTracks().forEach((track) => track.stop());
      if (video) video.srcObject = null;
    };
  }, [cameraStream]);

  useEffect(() => () => { cameraRequestRef.current = false; }, []);

  function saveObservations(next: PlantObservation[]) {
    setObservations(next);
    if (user && !writeObservations(user.id, next)) setNotice("Storage is full. Remove older photos and try again.");
  }

  async function deleteSelectedObservation() {
    if (!user || !selected || !observations.some((item) => item.id === selected.id)) return;
    if (selected.serverBacked) {
      try { await api.deleteObservation(selected.id); }
      catch { setNotice("Could not delete this observation from your account. Please try again."); return; }
    }
    saveObservations(observations.filter((item) => item.id !== selected.id));
    setSelected(null);
    setDeleteConfirm(false);
    setNotice("Your observation was deleted");
    window.setTimeout(() => setNotice(""), 3000);
  }

  function openObservation(observation: PlantObservation) {
    setDeleteConfirm(false);
    setSelected(observation);
  }

  const visible = useMemo(() => observations.filter((plant) => {
    const matches = `${plant.name} ${plant.scientific} ${plant.location} ${plant.family}`.toLowerCase().includes(query.toLowerCase()) && (partFilter === "All" || plant.plantPart === partFilter);
    if (filter === "Needs identification") return matches && plant.status !== "Identified";
    if (filter === "Identified") return matches && plant.status === "Identified";
    return matches;
  }).sort((a, b) => oldestFirst ? a.createdAt - b.createdAt : b.createdAt - a.createdAt), [filter, observations, oldestFirst, partFilter, query]);

  async function chooseFile(next: File | undefined) {
    if (!next) return;
    if (!next.type.match(/^image\/(jpeg|png|webp)$/)) { setIdentifyError("Choose a JPG, PNG, or WEBP image."); return; }
    setFile(next);
    setIdentification(null);
    setReference([]);
    setImage(URL.createObjectURL(next));
    setIdentifyError("");
    setStoredImage(null);
    try { setStoredImage(await compressedImage(next)); }
    catch (error) { setIdentifyError(error instanceof Error ? error.message : "Image preview failed."); }
  }

  async function startCamera() {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Camera access is unavailable. Open PlantMitra on HTTPS or localhost and allow camera permission.");
      return;
    }
    cameraRequestRef.current = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      if (!cameraRequestRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      setCameraStream(stream);
    } catch (error) {
      if (!cameraRequestRef.current) return;
      const cameraError = error as DOMException;
      setCameraError(cameraError.name === "NotAllowedError"
        ? "Camera permission was denied. Allow camera access in your browser settings, then try again."
        : cameraError.name === "NotFoundError"
          ? "No camera was found on this device."
          : "Could not open the camera. Check that it is connected and not being used by another app.");
    }
  }

  function captureCameraPhoto() {
    const video = cameraVideoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) {
      setCameraError("Camera is starting. Wait a moment and try again.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setCameraError("Photo capture is unavailable in this browser.");
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!cameraRequestRef.current) return;
      if (!blob) {
        setCameraError("Could not capture the photo. Please try again.");
        return;
      }
      const photo = new File([blob], `plant-photo-${Date.now()}.jpg`, { type: "image/jpeg" });
      cameraRequestRef.current = false;
      setCameraStream(null);
      void chooseFile(photo);
    }, "image/jpeg", 0.92);
  }

  function stopCamera() {
    cameraRequestRef.current = false;
    setCameraStream(null);
    setCameraError("");
  }

  function useCurrentLocation() {
    setGeoMessage("Finding your location…");
    if (!navigator.geolocation) { setGeoMessage("GPS is not available in this browser."); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords: position }) => {
        const current = { latitude: position.latitude, longitude: position.longitude, accuracy: position.accuracy };
        setCoordinates(current);
        setLocation(`${current.latitude.toFixed(5)}, ${current.longitude.toFixed(5)}`);
        setGeoMessage(`Location captured (about ${Math.round(current.accuracy)} m accuracy).`);
      },
      () => setGeoMessage("Location permission was not granted. You can enter a place manually."),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  }

  function clearCurrentLocation() {
    setCoordinates(undefined);
    setGeoMessage("");
    setLocation("");
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    chooseFile(event.dataTransfer.files[0]);
  }

  async function addObservation() {
    if (!image || !storedImage || !file) { setIdentifyError("Choose a JPG or PNG plant photo first."); return; }
    setBusy(true);
    setIdentifyError("");
    try {
      const data = new FormData();
      data.append("image", file);
      data.append("dataset_label", identification?.supported ? identification.dataset_label || "" : "");
      data.append("plant_part", plantPart);
      data.append("note", note.trim());
      data.append("location", location.trim());
      if (coordinates) {
        data.append("latitude", String(coordinates.latitude));
        data.append("longitude", String(coordinates.longitude));
        data.append("accuracy", String(coordinates.accuracy));
      }
      const saved = await api.saveObservation(data);
      const item = { ...saved, image: storedImage, serverBacked: true };
      saveObservations([item, ...observations]);
      setUploadOpen(false);
      setCameraStream(null);
      setSelected(item);
      setImage(null);
      setStoredImage(null);
      setFile(null);
      setNote("");
      setLocation("");
      setCoordinates(undefined);
      setGeoMessage("");
      setPlantPart("Leaf");
      setIdentification(null);
      setReference([]);
      setNotice("Observation saved to your account");
      window.setTimeout(() => setNotice(""), 3000);
    } catch (error) {
      setIdentifyError(error instanceof Error ? error.message : "Could not save this observation.");
    } finally { setBusy(false); }
  }

  async function identifyPlant() {
    if (!file) return;
    setBusy(true);
    setIdentifyError("");
    try {
      const data = new FormData();
      data.append("image", file);
      const result = await api.identifyPlant(data);
      setIdentification(result);
      setReference([]);
      if (result.supported && result.scientific_name) {
        setReferencesLoading(true);
        try { setReference((await api.referenceObservations(result.scientific_name)).observations); }
        catch { setReference([]); }
        finally { setReferencesLoading(false); }
      }
    } catch (error) {
      setIdentifyError(error instanceof Error ? error.message : "Identification failed.");
    } finally { setBusy(false); }
  }

  function resetUpload() { cameraRequestRef.current = false; setUploadOpen(false); setCameraStream(null); setCameraError(""); setImage(null); setStoredImage(null); setFile(null); setNote(""); setLocation(""); setCoordinates(undefined); setGeoMessage(""); setPlantPart("Leaf"); setIdentifyError(""); setIdentification(null); setReference([]); }

  if (loading || !user) return <div className="grid min-h-screen place-items-center bg-[#fbfcf8] text-sm text-[#68746a]">Loading your plant collection…</div>;

  const identifiedCount = observations.filter((item) => item.status === "Identified").length;
  const speciesCount = new Set(observations.filter((item) => item.status === "Identified").map((item) => item.scientific)).size;

  return (
    <main className="observations-app">
      <header className="topbar">
        <a className="brand" href="/home" aria-label="PlantMitra home"><span className="brand-mark">✳</span><span>Plant<span className="brand-light">Mitra</span></span></a>
        <nav className="top-nav" aria-label="Main navigation"><a className="nav-active" href="/home">Home</a><a href="/map">Map</a><a href="#collection">My observations</a><a href="/dashboard">Dashboard</a><a href="/character">Avatar</a></nav>
        <div className="top-actions"><span className="signed-in-name">{user.display_name}</span><a className="avatar-button" href="/settings" aria-label="Account settings">{user.display_name.trim().slice(0, 2).toUpperCase()}</a><button className="account-button signout-button" type="button" onClick={logout}>Sign out</button></div>
      </header>

      <div className="page-wrap">
        <section className="page-heading"><div><div className="eyebrow"><span className="eyebrow-dot" /> YOUR PLANT COLLECTION</div><h1>Welcome, {user.display_name.split(" ")[0]}</h1><p>Your observations and plant discoveries in one place.</p></div><button className="primary-button" onClick={() => setUploadOpen(true)}><span className="plus-icon">+</span> Scan a plant</button></section>
        <section className="stats-strip" aria-label="Your plant activity"><div className="stat"><span className="stat-symbol">◉</span><span><strong>{observations.length}</strong><small>your observations</small></span></div><div className="stat"><span className="stat-symbol stat-olive">✿</span><span><strong>{speciesCount}</strong><small>species identified</small></span></div><div className="stat"><span className="stat-symbol stat-terracotta">⌖</span><span><strong>{identifiedCount}</strong><small>successful matches</small></span></div><div className="community-note"><span className="online-dot" /> Saved to this account on this device</div></section>
        <section className="controls" aria-label="Filter observations"><div className="filter-tabs">{filters.map((item) => <button key={item} className={filter === item ? "filter-tab selected" : "filter-tab"} onClick={() => setFilter(item)}>{item}{item === "All observations" && <span className="tab-count">{observations.length}</span>}</button>)}</div><div className="control-right"><label className="search-box"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your plants..." aria-label="Search plants and places" /></label><label className="visually-hidden" htmlFor="plant-part-filter">Filter by plant part</label><select className="sort-button" id="plant-part-filter" value={partFilter} onChange={(event) => setPartFilter(event.target.value as PlantPart | "All")}><option value="All">All plant parts</option>{PLANT_PARTS.filter((part) => part !== "Aerial picture").map((part) => <option key={part}>{part}</option>)}</select><button className="sort-button" type="button" onClick={() => setOldestFirst((value) => !value)}>{oldestFirst ? "Oldest" : "Newest"} <span>⌄</span></button></div></section>

        <section className="observation-grid" id="collection" aria-label="Plant observations">{visible.map((plant) => <article className="observation-card" key={plant.id} onClick={() => openObservation(plant)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openObservation(plant)}><div className="card-image-wrap"><img className="card-image" src={plant.image} alt={`${plant.name} observation`} /><span className="organ-sticker" title={`Photo shows: ${plant.plantPart}`}><span aria-hidden="true">{PART_STICKERS[plant.plantPart]}</span>{plant.plantPart}</span><span className="image-location"><span>⌖</span> {plant.location}</span></div><div className="card-content"><div className="card-title-row"><div><h2>{plant.name}</h2><p className="scientific-name">{plant.scientific}</p></div>{plant.status === "Identified" && <span className="confidence" title="Identification confidence">{plant.confidence}%</span>}</div><div className="card-meta"><span className="family-tag">{plant.family}</span><span>{plant.date}</span></div></div></article>)}</section>
        {visible.length === 0 && <div className="empty-state"><span>{query ? "⌕" : "✳"}</span><h2>{query || observations.length ? "No observations found" : "Your collection is ready"}</h2><p>{query || observations.length ? "Try another plant name or clear your filters." : "Scan or upload a plant photo to make your first observation."}</p>{query || observations.length ? <button onClick={() => { setQuery(""); setFilter(filters[0]); }}>Clear filters</button> : <button className="primary-button" onClick={() => setUploadOpen(true)}>Scan your first plant</button>}</div>}
        <div className="load-more"><span>Showing {visible.length} of {observations.length} observations</span></div>
        <footer className="site-footer" id="about"><a className="footer-brand" href="/home">✳ PlantMitra</a><span>Plant knowledge, shared by everyone.</span><span>AI plant suggestions can be wrong. Never use a plant medicinally without expert confirmation.</span></footer>
      </div>

      {notice && <div role="status" className="toast">{notice}</div>}

      {uploadOpen && (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && resetUpload()}>
          <section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title">
            <div className="modal-header">
              <div><span className="modal-kicker">ADD TO THE COLLECTION</span><h2 id="upload-title">New observation</h2></div>
              <button className="icon-button" onClick={resetUpload} aria-label="Close">×</button>
            </div>
            <p className="modal-description">Share a clear photo of the plant. A close-up of its leaves works best.</p>
            <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event: ChangeEvent<HTMLInputElement>) => { void chooseFile(event.target.files?.[0]); event.target.value = ""; }} />
            {cameraStream ? <div className="live-camera-wrap"><video ref={cameraVideoRef} autoPlay playsInline muted aria-label="Live plant camera preview" /><div className="live-camera-actions"><button type="button" className="secondary-button" onClick={stopCamera}>Cancel camera</button><button type="button" className="primary-button" onClick={captureCameraPhoto}>Capture photo</button></div></div> : image ? <div className="preview-wrap"><img src={image} alt="Selected plant preview" /><div className="preview-actions"><button className="replace-photo" onClick={() => inputRef.current?.click()}>Choose another</button><button className="replace-photo" onClick={startCamera}>Take another</button></div></div> : <><button className="dropzone" onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}><span className="upload-icon">↑</span><strong>Choose a photo or drop it here</strong><span>JPG or PNG · up to 15 MB</span></button><button className="camera-capture-button" type="button" onClick={startCamera}><span aria-hidden="true">◎</span> Open camera</button></>}
            {cameraError && <p className="camera-error" role="alert">{cameraError}</p>}
            <div className="observation-fields">
              <label className="field-label">Plant part<select value={plantPart} onChange={(event) => setPlantPart(event.target.value as PlantPart)}>{PLANT_PARTS.map((part) => <option key={part}>{part}</option>)}</select></label>
              <div className="location-field"><label className="field-label" htmlFor="observation-location">Location <span>Optional</span><input id="observation-location" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="City, region, or GPS coordinates" /></label><button className="gps-capture-button" type="button" onClick={useCurrentLocation} title="Allow location access to attach GPS coordinates">⌖ Use current GPS</button>{geoMessage && <small className="gps-status" role="status">{geoMessage}</small>}</div>
            </div>
            {coordinates && <div className="upload-gps-map"><div><strong>Photo location</strong><small>{coordinates.latitude.toFixed(5)}, {coordinates.longitude.toFixed(5)} · ±{Math.round(coordinates.accuracy)} m</small><button type="button" onClick={clearCurrentLocation}>Remove GPS</button></div><iframe title="Map preview of the photo GPS location" loading="lazy" referrerPolicy="no-referrer" src={`https://www.openstreetmap.org/export/embed.html?bbox=${coordinates.longitude - 0.025}%2C${coordinates.latitude - 0.015}%2C${coordinates.longitude + 0.025}%2C${coordinates.latitude + 0.015}&layer=mapnik&marker=${coordinates.latitude}%2C${coordinates.longitude}`} /></div>}
            {identification && <section className="ai-result-panel" aria-live="polite">
              <span className="modal-kicker">PLANTMITRA MODEL · v{identification.model_version}</span>
              {identification.supported && identification.plant_information ? <>
                <h3>{identification.plant_information.common_name}</h3>
                <p className="detail-scientific">{identification.plant_information.scientific_name}</p>
                {identification.plant_information.taxonomy_note && <p className="confidence-note">{identification.plant_information.taxonomy_note}</p>}
                <p>{Math.round(identification.confidence * 100)}% model confidence · {identification.plant_information.family}</p>
                <p className="confidence-note">{identification.confidence_note}</p>
                <h4>Plant details</h4>
                <p>{identification.plant_information.description}</p>
                <dl className="result-facts"><div><dt>Type</dt><dd>{identification.plant_information.plant_type}</dd></div><div><dt>Parts</dt><dd>{identification.plant_information.plant_parts.join(", ")}</dd></div><div><dt>Habitat</dt><dd>{identification.plant_information.habitat}</dd></div><div><dt>Distribution</dt><dd>{identification.plant_information.distribution}</dd></div></dl>
                <h4>Traditional / documented uses</h4>
                {identification.plant_information.traditional_uses.map((text) => <p key={text}>{text}</p>)}
                <p className="confidence-note">Plant part above is your selection; this model does not classify plant organs.</p>
                <div className="source-links">Sources: {identification.plant_information.sources.map((source) => <a key={source} href={source} target="_blank" rel="noreferrer">Kew POWO ↗</a>)}</div>
                <h4>Reference observations</h4>
                {referencesLoading ? <p>Loading reference records…</p> : reference.length ? <div className="reference-grid">{reference.slice(0, 6).map((item) => <a className="reference-item" key={item.id} href={item.source_url} target="_blank" rel="noreferrer"><img src={item.image} alt={`Reference ${item.scientific_name}`} loading="lazy" /><span>{item.location || "Location not provided"}</span><small>{item.date || "Date not provided"} · {item.license}</small><small>{item.attribution || "Attribution not provided"}</small></a>)}</div> : <p>Reference observations are temporarily unavailable.</p>}
                <a className="source-links" href="https://www.gbif.org/" target="_blank" rel="noreferrer">Reference source: GBIF ↗</a>
              </> : <><h3>Plant identification is uncertain</h3><p>{identification.message || "Try another photo with clearer plant features."}</p><p>{Math.round(identification.confidence * 100)}% model confidence. This model supports only its seven listed classes.</p></>}
              {identification.top_predictions.length > 0 && <p className="confidence-note">Top model suggestions: {identification.top_predictions.map((item) => `${item.class} (${Math.round(item.confidence * 100)}%)`).join(" · ")}</p>}
            </section>}
            <label className="field-label">Observation note <span>Optional</span><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add details about this plant..." rows={3} /></label>
            {identifyError && <p className="form-error" role="alert">{identifyError}</p>}
            <div className="modal-actions"><button className="secondary-button" onClick={resetUpload}>Cancel</button><button className="secondary-button identify-button" disabled={!file || !storedImage || busy || Boolean(cameraStream)} onClick={identifyPlant}>{busy && !identification ? "Identifying…" : "Identify plant"}</button><button className="primary-button" onClick={addObservation} disabled={!storedImage || busy || Boolean(cameraStream)}>{busy && identification ? "Saving…" : "Save observation"}</button></div>
            <p className="privacy-note">Identification uses PlantMitra’s seven-class model. Your photo and permitted GPS coordinates are saved to your signed-in account when you choose Save observation. Reference records are fetched separately from GBIF.</p>
          </section>
        </div>
      )}

      {selected && <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><aside className="detail-drawer" aria-label="Observation details"><button className="icon-button drawer-close" onClick={() => setSelected(null)} aria-label="Close details">×</button><img className="detail-image" src={selected.image} alt={selected.name} /><div className="detail-body"><span className="modal-kicker">PLANT OBSERVATION</span><h2>{selected.name}</h2><p className="detail-scientific">{selected.scientific}</p><div className="detail-status">{selected.status === "Identified" ? `✓ ${selected.confidence}% match` : "◷ Needs identification"}</div><dl className="detail-list"><div><dt>Plant part</dt><dd><span className="detail-organ-sticker">{PART_STICKERS[selected.plantPart]} {selected.plantPart}</span></dd></div><div><dt>Family</dt><dd>{selected.family}</dd></div><div><dt>Location</dt><dd>{selected.location}</dd></div>{selected.coordinates && <div><dt>GPS coordinates</dt><dd>{selected.coordinates.latitude.toFixed(5)}, {selected.coordinates.longitude.toFixed(5)}<br /><a className="gps-map-link" href={`https://www.openstreetmap.org/?mlat=${selected.coordinates.latitude}&mlon=${selected.coordinates.longitude}#map=16/${selected.coordinates.latitude}/${selected.coordinates.longitude}`} target="_blank" rel="noreferrer">Open map ↗</a></dd></div>}<div><dt>Observed</dt><dd>{selected.date}</dd></div></dl>{selected.plantInformation && <section className="saved-plant-info"><h3>Plant information</h3><p>{selected.plantInformation.description}</p><p><strong>Habitat:</strong> {selected.plantInformation.habitat}</p><p><strong>Distribution:</strong> {selected.plantInformation.distribution}</p>{selected.plantInformation.sources.map((source) => <a key={source} href={source} target="_blank" rel="noreferrer">Kew POWO source ↗</a>)}</section>}<div className="detail-disclaimer">AI suggestions may be wrong, even when confidence is high. Do not eat or use a plant medicinally based on this result. Confirm identification with a qualified botanist and consult a healthcare professional before medicinal use.</div><button className="secondary-button detail-share" onClick={() => { navigator.clipboard?.writeText(`${selected.name} — ${selected.scientific}`); setNotice("Plant details copied"); }}>↗ Copy plant details</button>{deleteConfirm ? <div className="delete-confirm" role="group" aria-label="Confirm observation deletion"><p>Delete this observation from your collection? This cannot be undone.</p><div><button className="secondary-button" onClick={() => setDeleteConfirm(false)}>Cancel</button><button className="delete-observation-button" onClick={deleteSelectedObservation}>Delete observation</button></div></div> : <button className="delete-observation-button" type="button" onClick={() => setDeleteConfirm(true)}><span aria-hidden="true">⌫</span> Delete observation</button>}</div></aside></div>}
    </main>
  );
}
