import type { PlantInformation } from "@/lib/api";

export const PLANT_PARTS = ["Leaf", "Flower", "Fruit", "Seed", "Bark", "Root", "Stem", "Habit", "Branch", "Bud", "Aerial", "Other", "Aerial picture"] as const;
export type PlantPart = (typeof PLANT_PARTS)[number];

export type PlantObservation = {
  id: number;
  name: string;
  scientific: string;
  location: string;
  date: string;
  image: string;
  image_url?: string;
  family: string;
  confidence: number;
  status: string;
  createdAt: number;
  plantPart: PlantPart;
  coordinates?: { latitude: number; longitude: number; accuracy: number };
  note?: string;
  plantInformation?: PlantInformation | null;
  serverBacked?: boolean;
};

const storageKey = (userId: string) => `plantmitra_observations_${userId}`;

export function readObservations(userId: string): PlantObservation[] {
  try {
    const value = localStorage.getItem(storageKey(userId));
    if (!value) return [];
    const parsed = JSON.parse(value) as Array<Partial<PlantObservation>>;
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => ({
      ...item,
      id: Number(item.id) || Date.now(),
      name: item.name || "Unidentified plant",
      scientific: item.scientific || "Not identified",
      location: item.location || "Location not added",
      date: item.date || "Date unavailable",
      image: item.image || "",
      family: item.family || "Unknown",
      confidence: Number(item.confidence) || 0,
      status: item.status || "Needs identification",
      createdAt: Number(item.createdAt) || Date.parse(item.date || "") || 0,
      plantPart: PLANT_PARTS.includes(item.plantPart as PlantPart) ? item.plantPart as PlantPart : "Other",
    }));
  } catch {
    return [];
  }
}

export function writeObservations(userId: string, observations: PlantObservation[]): boolean {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(observations));
    return true;
  } catch {
    return false;
  }
}
