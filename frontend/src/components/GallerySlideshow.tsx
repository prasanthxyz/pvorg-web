import { useEffect, useMemo, useRef, useState } from "react";

interface GallerySlideshowProps {
  images: string[];
}

export default function GallerySlideshow({ images }: GallerySlideshowProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const shuffled = useMemo(() => {
    const arr = [...images];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }, [images]);

  useEffect(() => {
    setCurrentIndex(0);
    if (timerRef.current) clearInterval(timerRef.current);
    if (shuffled.length <= 1) return;

    timerRef.current = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % shuffled.length);
    }, 2000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [shuffled]);

  if (shuffled.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-secondary)" }}>
        No images
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      <img
        key={shuffled[currentIndex]}
        src={shuffled[currentIndex]}
        alt={`Gallery ${currentIndex + 1}`}
        style={{
          maxWidth: "100%",
          maxHeight: "100%",
          objectFit: "contain",
          transition: "opacity 0.3s ease",
        }}
      />
    </div>
  );
}
