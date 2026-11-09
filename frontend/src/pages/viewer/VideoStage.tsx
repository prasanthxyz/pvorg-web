import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Button } from "../../components/controls";
import { EmptyState } from "../../components/feedback";
import { Icon } from "../../components/Icon";
import type { ViewerCombination } from "../../api/types";
import { timecode } from "../../app/format";

export interface PlayerHandle {
  togglePlay(): void;
  pause(): void;
  play(): void;
  seekBy(seconds: number): void;
  seekToFraction(fraction: number): void;
  isPlaying(): boolean;
  isReady(): boolean;
}

interface Cue {
  start: number;
  end: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

function parseVtt(text: string): Cue[] {
  const toSeconds = (t: string) => {
    const [h, m, s] = t.split(":");
    return Number(h) * 3600 + Number(m) * 60 + Number(s);
  };
  const cues: Cue[] = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const time = lines[i].match(/^(\d+:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d+:\d{2}:\d{2}\.\d{3})/);
    const rect = lines[i + 1]?.match(/#xywh=(\d+),(\d+),(\d+),(\d+)/);
    if (time && rect) {
      cues.push({ start: toSeconds(time[1]), end: toSeconds(time[2]), x: +rect[1], y: +rect[2], w: +rect[3], h: +rect[4] });
    }
  }
  return cues;
}

const UNPLAYABLE = new Set(["mkv", "avi", "wmv", "flv"]);

interface Props {
  combination: ViewerCombination;
  active: boolean;
  onShowContactSheet: () => void;
}

/** The video and its transport bar (SPEC §5, §9). */
export const VideoStage = forwardRef<PlayerHandle, Props>(function VideoStage(
  { combination, active, onShowContactSheet },
  ref,
) {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const { video: info } = combination;

  useImperativeHandle(ref, () => ({
    togglePlay: () => (video.current?.paused ? play() : video.current?.pause()),
    pause: () => video.current?.pause(),
    play,
    seekBy: (s) => seek((video.current?.currentTime ?? 0) + s),
    seekToFraction: (f) => seek(f * (video.current?.duration ?? 0)),
    isPlaying: () => !!video.current && !video.current.paused,
    isReady: () => !failed && !!video.current && Number.isFinite(video.current.duration),
  }));

  function play() {
    const el = video.current;
    if (!el || failed) return;
    if (el.ended) el.currentTime = 0;
    el.play().catch(() => undefined);
  }

  function seek(seconds: number) {
    const el = video.current;
    if (!el || !Number.isFinite(el.duration)) return;
    el.currentTime = Math.max(0, Math.min(el.duration, seconds));
    setTime(el.currentTime);
  }

  useEffect(() => {
    if (active) play();
    else video.current?.pause();
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  if (failed) {
    const ext = info.extension;
    return (
      <div className="stage__state">
        <EmptyState
          icon="warning"
          tone="warning"
          title="Can’t Play This Video"
          actions={
            <>
              <a className="btn btn--primary btn--md" href={info.videoUrl} download={info.filename}>
                <Icon name="download" size={18} />
                <span className="btn__label">Download Video</span>
              </a>
              <Button onClick={onShowContactSheet}>Show Contact Sheet</Button>
            </>
          }
        >
          {UNPLAYABLE.has(ext)
            ? `Your browser can’t play .${ext} files. Download the video to open it in another app, or re-encode it to MP4.`
            : "The video couldn’t be opened. The file may be damaged or use a codec your browser doesn’t support."}
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="player">
      <div className="player__video">
        <video
          ref={video}
          src={info.videoUrl}
          preload="metadata"
          playsInline
          aria-label={`Video: ${info.title}`}
          onClick={() => (video.current?.paused ? play() : video.current?.pause())}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onDurationChange={(e) => setDuration(Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : 0)}
          onLoadedMetadata={() => setLoading(false)}
          onWaiting={() => setLoading(true)}
          onCanPlay={() => setLoading(false)}
          onError={() => setFailed(true)}
        />
        {loading && <span className="player__spinner" aria-hidden="true" />}
      </div>
      <div className="transport">
        <div className="transport__buttons">
          <button type="button" className="transport__btn" aria-label="Skip back 10 seconds" title="Skip back 10 seconds (←)"
            onClick={() => seek(time - 10)}>
            <Icon name="back10" size={20} />
          </button>
          <button type="button" className="transport__btn transport__btn--primary" aria-label={playing ? "Pause" : "Play"}
            title={`${playing ? "Pause" : "Play"} (Space)`}
            onClick={() => (playing ? video.current?.pause() : play())}>
            <Icon name={playing ? "pause" : "play"} size={20} />
          </button>
          <button type="button" className="transport__btn" aria-label="Skip forward 10 seconds"
            title="Skip forward 10 seconds (→)" onClick={() => seek(time + 10)}>
            <Icon name="forward10" size={20} />
          </button>
        </div>
        <span className="transport__time tabular">{timecode(time)}</span>
        <Scrubber time={time} duration={duration} spriteUrl={info.spriteUrl} vttUrl={info.vttUrl} onSeek={seek} />
        <span className="transport__time tabular">{timecode(duration)}</span>
      </div>
    </div>
  );
});

function Scrubber({
  time,
  duration,
  spriteUrl,
  vttUrl,
  onSeek,
}: {
  time: number;
  duration: number;
  spriteUrl: string | null;
  vttUrl: string | null;
  onSeek: (seconds: number) => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ x: number; width: number; time: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [cues, setCues] = useState<Cue[]>([]);

  useEffect(() => {
    setCues([]);
    if (!vttUrl) return;
    let cancelled = false;
    fetch(vttUrl)
      .then((r) => (r.ok ? r.text() : ""))
      .then((text) => !cancelled && setCues(parseVtt(text)))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [vttUrl]);

  const at = (clientX: number) => {
    const rect = track.current!.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return { x: fraction * rect.width, width: rect.width, time: fraction * duration };
  };

  const progress = duration > 0 ? Math.min(1, time / duration) : 0;
  const cue = hover ? cues.find((c) => hover.time >= c.start && hover.time < c.end) ?? cues.at(-1) : undefined;
  const previewWidth = 224;
  const scale = cue ? previewWidth / cue.w : 1;

  return (
    <div
      ref={track}
      className={`scrubber${hover || dragging ? " is-active" : ""}`}
      role="slider"
      tabIndex={0}
      aria-label="Playback position"
      aria-valuemin={0}
      aria-valuemax={Math.round(duration)}
      aria-valuenow={Math.round(time)}
      aria-valuetext={`${timecode(time)} of ${timecode(duration)}`}
      onPointerMove={(e) => {
        if (duration <= 0) return;
        const point = at(e.clientX);
        setHover(point);
        if (dragging) onSeek(point.time);
      }}
      onPointerLeave={() => !dragging && setHover(null)}
      onPointerDown={(e) => {
        if (duration <= 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        setDragging(true);
        onSeek(at(e.clientX).time);
      }}
      onPointerUp={(e) => {
        setDragging(false);
        onSeek(at(e.clientX).time);
        if (e.pointerType !== "mouse") setHover(null);
      }}
      onPointerCancel={() => {
        setDragging(false);
        setHover(null);
      }}
      onKeyDown={(e) => {
        const step = { ArrowLeft: -10, ArrowRight: 10, ArrowDown: -10, ArrowUp: 10 }[e.key];
        if (step !== undefined) {
          e.preventDefault();
          onSeek(time + step);
        } else if (e.key === "Home" || e.key === "End") {
          e.preventDefault();
          onSeek(e.key === "Home" ? 0 : duration);
        }
      }}
    >
      <div className="scrubber__track">
        <div className="scrubber__fill" style={{ width: `${progress * 100}%` }} />
        <div className="scrubber__knob" style={{ left: `${progress * 100}%` }} />
      </div>
      {hover && duration > 0 && (
        <div
          className="scrubber__preview"
          style={{ left: Math.max(0, Math.min(hover.width - previewWidth, hover.x - previewWidth / 2)) }}
          aria-hidden="true"
        >
          {cue && spriteUrl && (
            <div className="scrubber__frame" style={{ width: previewWidth, height: cue.h * scale }}>
              <SpriteFrame spriteUrl={spriteUrl} cue={cue} scale={scale} />
            </div>
          )}
          <span className="scrubber__time tabular">{timecode(hover.time)}</span>
        </div>
      )}
    </div>
  );
}

/** Draws one sprite tile at the preview size (background-size needs the sheet's natural size). */
function SpriteFrame({ spriteUrl, cue, scale }: { spriteUrl: string; cue: Cue; scale: number }) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const img = new Image();
    img.onload = () => setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    img.src = spriteUrl;
  }, [spriteUrl]);
  if (!natural) return null;
  return (
    <span
      className="scrubber__tile"
      style={{
        backgroundImage: `url("${spriteUrl}")`,
        backgroundSize: `${natural.w * scale}px ${natural.h * scale}px`,
        backgroundPosition: `${-cue.x * scale}px ${-cue.y * scale}px`,
      }}
    />
  );
}
