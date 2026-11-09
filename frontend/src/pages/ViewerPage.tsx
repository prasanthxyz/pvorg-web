import { useCallback, useEffect, useRef, useState } from "react";
import { useCombinations } from "../hooks/useCombinations";
import VideoPlayer, { type VideoPlayerHandle } from "../components/VideoPlayer";
import TgpView from "../components/TgpView";
import GallerySlideshow from "../components/GallerySlideshow";

export default function ViewerPage() {
  const { combination, next, prev } = useCombinations();
  const [isTgpShown, setIsTgpShown] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const videoRef = useRef<VideoPlayerHandle>(null);

  const handleNext = useCallback(() => {
    setIsPlaying(false);
    setIsTgpShown(true);
    next();
  }, [next]);

  const handlePrev = useCallback(() => {
    setIsPlaying(false);
    setIsTgpShown(true);
    prev();
  }, [prev]);

  const handleToggleTgp = useCallback(() => {
    setIsTgpShown((prev) => {
      if (prev) {
        setIsPlaying(true);
      } else {
        setIsPlaying(false);
      }
      return !prev;
    });
  }, []);

  const handleTogglePlay = useCallback(() => {
    setIsPlaying((p) => !p);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case "p":
          e.preventDefault();
          handleToggleTgp();
          break;
        case "b":
          e.preventDefault();
          handlePrev();
          break;
        case "n":
          e.preventDefault();
          handleNext();
          break;
        case " ":
          e.preventDefault();
          if (!isTgpShown) handleTogglePlay();
          break;
        case "ArrowLeft":
          e.preventDefault();
          if (!isTgpShown) videoRef.current?.seekRelative(-10);
          break;
        case "ArrowRight":
          e.preventDefault();
          if (!isTgpShown) videoRef.current?.seekRelative(10);
          break;
        default:
          if (!isTgpShown && e.key >= "0" && e.key <= "9") {
            e.preventDefault();
            videoRef.current?.seekToPercent(parseInt(e.key) / 10);
          }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleNext, handlePrev, handleToggleTgp, handleTogglePlay, isTgpShown]);

  if (!combination) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 24 }}>
        No combinations found.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "8px 16px",
          gap: 12,
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}
      >
        <div style={{ flex: 1, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {combination.video.filename}
        </div>

        <button
          onClick={handleToggleTgp}
          style={{
            padding: "4px 12px",
            borderRadius: 6,
            background: "var(--accent)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          {isTgpShown ? "VID" : "TGP"}
        </button>

        <button onClick={handlePrev} style={navBtnStyle}>
          Prev
        </button>
        <button onClick={handleNext} style={navBtnStyle}>
          Next
        </button>

        <div
          style={{
            fontWeight: 500,
            color: "var(--text-secondary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 200,
          }}
        >
          {combination.gallery.name}
        </div>

        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          {combination.index + 1}/{combination.total}
        </div>
      </div>

      {/* Main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Video / TGP area (75%) */}
        <div style={{ width: "75%", height: "100%", overflow: "hidden" }}>
          {isTgpShown ? (
            <TgpView tgpUrl={combination.video.tgp_url} />
          ) : (
            <VideoPlayer
              ref={videoRef}
              videoUrl={combination.video.url}
              isPlaying={isPlaying}
              onTogglePlay={handleTogglePlay}
              spriteUrl={combination.video.sprite_url}
              spriteVttUrl={combination.video.sprite_vtt_url}
            />
          )}
        </div>

        {/* Gallery slideshow (25%) */}
        <div
          style={{
            width: "25%",
            height: "100%",
            borderLeft: "1px solid var(--border)",
            overflow: "hidden",
          }}
        >
          <GallerySlideshow images={combination.gallery.images} />
        </div>
      </div>
    </div>
  );
}

const navBtnStyle: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: 6,
  background: "var(--tag-bg)",
  color: "var(--text-primary)",
  fontSize: 13,
  fontWeight: 500,
};
