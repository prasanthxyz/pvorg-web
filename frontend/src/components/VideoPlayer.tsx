import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

const FALLBACK_TILE_WIDTH = 160;
const FALLBACK_TILE_HEIGHT = 90;
const FALLBACK_COLS = 10;
const FALLBACK_INTERVAL = 2;

interface SpriteCue {
  start: number;
  end: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

function parseVttTime(v: string): number {
  const [hh, mm, ssMs] = v.split(":");
  const [ss, ms] = ssMs.split(".");
  return (
    Number(hh || 0) * 3600
    + Number(mm || 0) * 60
    + Number(ss || 0)
    + Number(ms || 0) / 1000
  );
}

function parseSpriteVtt(text: string): SpriteCue[] {
  const lines = text.split(/\r?\n/);
  const cues: SpriteCue[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const timeLine = lines[i]?.trim() ?? "";
    if (!timeLine.includes("-->")) continue;
    const xywhLine = lines[i + 1]?.trim() ?? "";
    const timeMatch = timeLine.match(
      /^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})$/,
    );
    const xywhMatch = xywhLine.match(/#xywh=(\d+),(\d+),(\d+),(\d+)/);
    if (!timeMatch || !xywhMatch) continue;
    cues.push({
      start: parseVttTime(timeMatch[1]),
      end: parseVttTime(timeMatch[2]),
      x: Number(xywhMatch[1]),
      y: Number(xywhMatch[2]),
      w: Number(xywhMatch[3]),
      h: Number(xywhMatch[4]),
    });
  }
  return cues;
}

interface VideoPlayerProps {
  videoUrl: string;
  isPlaying: boolean;
  onTogglePlay: () => void;
  spriteUrl?: string;
  spriteVttUrl?: string;
}

export interface VideoPlayerHandle {
  seekToPercent: (pct: number) => void;
  seekRelative: (seconds: number) => void;
}

const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  ({ videoUrl, isPlaying, onTogglePlay, spriteUrl, spriteVttUrl }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const seekBarRef = useRef<HTMLDivElement>(null);
    const [progress, setProgress] = useState(0);
    const [spriteCues, setSpriteCues] = useState<SpriteCue[]>([]);
    const [hoverInfo, setHoverInfo] = useState<{
      x: number;
      time: number;
    } | null>(null);

    useImperativeHandle(ref, () => ({
      seekToPercent(pct: number) {
        const el = videoRef.current;
        if (!el || !isFinite(el.duration)) return;
        el.currentTime = el.duration * pct;
      },
      seekRelative(seconds: number) {
        const el = videoRef.current;
        if (!el) return;
        el.currentTime = Math.max(0, Math.min(el.duration, el.currentTime + seconds));
      },
    }));

    useEffect(() => {
      const el = videoRef.current;
      if (!el) return;
      if (isPlaying) {
        el.play().catch(() => {});
      } else {
        el.pause();
      }
    }, [isPlaying]);

    useEffect(() => {
      const el = videoRef.current;
      if (!el) return;
      el.pause();
      el.load();
      if (isPlaying) {
        el.play().catch(() => {});
      }
      setProgress(0);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoUrl]);

    useEffect(() => {
      const el = videoRef.current;
      if (!el) return;
      const onTime = () => {
        if (el.duration && isFinite(el.duration)) {
          setProgress(el.currentTime / el.duration);
        }
      };
      el.addEventListener("timeupdate", onTime);
      return () => el.removeEventListener("timeupdate", onTime);
    }, [videoUrl]);

    useEffect(() => {
      let cancelled = false;
      if (!spriteVttUrl) {
        setSpriteCues([]);
        return () => {
          cancelled = true;
        };
      }
      fetch(spriteVttUrl)
        .then((res) => (res.ok ? res.text() : Promise.reject(new Error("VTT fetch failed"))))
        .then((text) => {
          if (!cancelled) setSpriteCues(parseSpriteVtt(text));
        })
        .catch(() => {
          if (!cancelled) setSpriteCues([]);
        });
      return () => {
        cancelled = true;
      };
    }, [spriteVttUrl, videoUrl]);

    const handleSeekBarMouse = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        const bar = seekBarRef.current;
        const el = videoRef.current;
        if (!bar || !el || !isFinite(el.duration)) return;
        const rect = bar.getBoundingClientRect();
        const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
        const pct = x / rect.width;
        const time = pct * el.duration;
        setHoverInfo({ x, time });
      },
      [],
    );

    const handleSeekBarClick = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        const bar = seekBarRef.current;
        const el = videoRef.current;
        if (!bar || !el || !isFinite(el.duration)) return;
        const rect = bar.getBoundingClientRect();
        const pct = Math.max(0, Math.min((e.clientX - rect.left) / rect.width, 1));
        el.currentTime = pct * el.duration;
      },
      [],
    );

    const matchedCue = hoverInfo
      ? spriteCues.find((cue) => hoverInfo.time >= cue.start && hoverInfo.time < cue.end)
      : undefined;
    const fallbackFrame = hoverInfo
      ? Math.floor(hoverInfo.time / FALLBACK_INTERVAL)
      : 0;
    const fallbackCol = fallbackFrame % FALLBACK_COLS;
    const fallbackRow = Math.floor(fallbackFrame / FALLBACK_COLS);
    const previewWidth = matchedCue?.w ?? FALLBACK_TILE_WIDTH;
    const previewHeight = matchedCue?.h ?? FALLBACK_TILE_HEIGHT;
    const previewX = matchedCue?.x ?? fallbackCol * FALLBACK_TILE_WIDTH;
    const previewY = matchedCue?.y ?? fallbackRow * FALLBACK_TILE_HEIGHT;

    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#000",
        }}
      >
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            minHeight: 0,
          }}
        >
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            onClick={onTogglePlay}
            style={{ maxWidth: "100%", maxHeight: "100%", outline: "none" }}
            preload="auto"
          />
        </div>

        {/* Custom seek bar with sprite preview */}
        <div
          ref={seekBarRef}
          onMouseMove={handleSeekBarMouse}
          onMouseLeave={() => setHoverInfo(null)}
          onClick={handleSeekBarClick}
          style={{
            position: "relative",
            height: 8,
            background: "#333",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${progress * 100}%`,
              background: "var(--accent, #0a84ff)",
              pointerEvents: "none",
            }}
          />

          {hoverInfo && spriteUrl && (
            <div
              style={{
                position: "absolute",
                bottom: 12,
                left: Math.max(
                  0,
                  Math.min(
                    hoverInfo.x - previewWidth / 2,
                    (seekBarRef.current?.clientWidth ?? 0) - previewWidth,
                  ),
                ),
                width: previewWidth,
                height: previewHeight,
                backgroundImage: `url(${spriteUrl})`,
                backgroundPosition: `-${previewX}px -${previewY}px`,
                backgroundRepeat: "no-repeat",
                border: "2px solid #fff",
                borderRadius: 4,
                boxShadow: "0 2px 8px rgba(0,0,0,0.7)",
                pointerEvents: "none",
              }}
            />
          )}
        </div>
      </div>
    );
  },
);

VideoPlayer.displayName = "VideoPlayer";
export default VideoPlayer;
