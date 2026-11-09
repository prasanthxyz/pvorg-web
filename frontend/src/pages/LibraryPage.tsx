import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { LibraryState, VideoSummary } from "../api/types";
import { counted, humanize, joinNames, matches, setPageTitle } from "../app/format";
import { usePageShortcuts } from "../app/shortcuts";
import { useScrollBox, visibleRange } from "../app/virtual";
import { Button, SearchField } from "../components/controls";
import { ConfirmDialog, Dialog } from "../components/Dialog";
import { Callout, EmptyState, PageHeader } from "../components/feedback";
import { Icon } from "../components/Icon";
import { openMenuAt } from "../components/Menu";
import { hoverPreviewHandlers, openPreview } from "../components/Preview";
import { Thumbnail } from "../components/Thumbnail";
import { bumpData, dataVersion, showError, showToast, alert as alertStore } from "../state/feedback";
import { keepOnly, librarySearch, librarySelection, toggleSelection } from "../state/library";
import { commandKey, refreshStatus, reloadLibrary } from "../state/status";
import { useStore } from "../state/store";

const CARD_MIN = 220;
const CARD_MAX = 320;
const GAP_X = 16;
const GAP_Y = 24;
const PADDING = 24;
const TEXT_HEIGHT = 52;

function searchFields(v: VideoSummary): string[] {
  return [v.title, v.filename, humanize(v.studio), ...v.actors.map(humanize)];
}

export default function LibraryPage() {
  const version = useStore(dataVersion);
  const query = useStore(librarySearch);
  const selection = useStore(librarySelection);
  const [library, setLibrary] = useState<LibraryState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setPageTitle("Library");
    let cancelled = false;
    api.library().then((l) => !cancelled && setLibrary(l)).catch((e) => showError("Couldn’t Load the Library", e));
    return () => {
      cancelled = true;
    };
  }, [version]);

  const visible = useMemo(
    () => (library ? library.videos.filter((v) => matches(query, searchFields(v))) : []),
    [library, query],
  );
  const visibleNames = useMemo(() => new Set(visible.map((v) => v.filename)), [visible]);

  // What you see is what you delete: hidden videos leave the selection (SPEC §3.8).
  useEffect(() => {
    if (library) keepOnly(visibleNames);
  }, [library, visibleNames]);

  const allSelected = visible.length > 0 && visible.every((v) => selection.has(v.filename));
  const selectAll = () => librarySelection.set(new Set(visibleNames));
  const deselectAll = () => librarySelection.set(new Set());
  const requestDelete = (names: string[]) => names.length && setPendingDelete(names);

  usePageShortcuts((e, { mod, editing }) => {
    if (editing) return false;
    if (mod && e.key.toLowerCase() === "a") return visible.length > 0 && (selectAll(), true);
    if (mod && e.key === "Backspace") return selection.size > 0 && (requestDelete([...selection]), true);
    if (!mod && e.key === "Escape" && selection.size > 0) return deselectAll(), true;
    return false;
  });

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      const result = await api.deleteVideos(pendingDelete);
      setPendingDelete(null);
      librarySelection.set(new Set());
      if (result.errors.length) {
        alertStore.set({
          title: "Some Videos Couldn’t Be Deleted",
          message: `Deleted ${counted(result.deleted, "video")}.\n\n${result.errors.join("\n")}`,
        });
      } else {
        showToast(`Deleted ${counted(result.deleted, "video")}`, "trash");
      }
      bumpData();
      void refreshStatus();
    } catch (error) {
      setPendingDelete(null);
      showError("Delete Failed", error);
    } finally {
      setDeleting(false);
    }
  };

  const total = library?.videos.length ?? 0;
  const subtitle = !library
    ? ""
    : selection.size
      ? `${selection.size.toLocaleString()} of ${counted(total, "video")} selected`
      : query.trim()
        ? `${visible.length.toLocaleString()} of ${counted(total, "video")}`
        : counted(total, "video");

  const titles = new Map(library?.videos.map((v) => [v.filename, v.title]) ?? []);
  const deleteTitle = pendingDelete
    ? pendingDelete.length === 1
      ? `Delete “${titles.get(pendingDelete[0]) ?? pendingDelete[0]}”?`
      : `Delete ${counted(pendingDelete.length, "Video")}?`
    : "";

  return (
    <div className="library">
      <PageHeader
        title="Library"
        subtitle={subtitle}
        actions={
          <>
            <SearchField value={query} onChange={librarySearch.set} placeholder="Search Videos" label="Search videos" />
            <Button icon="checkCircle" disabled={!visible.length || allSelected} onClick={selectAll}
              title={`Select every ${query.trim() ? "matching " : ""}video (${commandKey()}A)`}>
              Select All
            </Button>
            <Button icon="xCircle" disabled={!selection.size} onClick={deselectAll} title="Deselect all videos (Esc)">
              Deselect All
            </Button>
            <Button variant="danger" icon="trash" disabled={!selection.size}
              onClick={() => requestDelete([...selection])} title={`Delete the selected videos (${commandKey()}⌫)`}>
              Delete
            </Button>
          </>
        }
      />
      {library && (
        <LibraryBody
          library={library}
          visible={visible}
          query={query}
          selection={selection}
          onShowSkipped={() => setShowSkipped(true)}
          onDelete={requestDelete}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={deleteTitle}
        destructive
        icon="trash"
        busy={deleting}
        confirmLabel={deleteTitle.replace(/\?$/, "")}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
        message={
          <>
            {pendingDelete && pendingDelete.length > 1 && pendingDelete.length <= 6 && (
              <p className="dialog__names">{joinNames(pendingDelete.map((f) => titles.get(f) ?? f))}.</p>
            )}
            <p>
              The video files, their contact sheets, mapping decisions and cached metadata will be permanently removed.
              This can’t be undone.
            </p>
          </>
        }
      />
      <Dialog open={showSkipped} onClose={() => setShowSkipped(false)} labelledBy="skipped-title" className="dialog--wide">
        {library && (
          <>
            <div className="dialog__body dialog__body--left">
              <h2 id="skipped-title" className="dialog__title">
                Skipped Files
              </h2>
              <ul className="skipped-list">
                {library.skipped.map((file) => (
                  <li key={file.filename}>
                    <span className="skipped-list__name">{file.filename}</span>
                    <span className="skipped-list__reasons">{file.reasons.join(" · ")}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="dialog__actions">
              <Button variant="primary" data-autofocus onClick={() => setShowSkipped(false)}>
                Done
              </Button>
            </div>
          </>
        )}
      </Dialog>
    </div>
  );
}

function LibraryBody({
  library,
  visible,
  query,
  selection,
  onShowSkipped,
  onDelete,
}: {
  library: LibraryState;
  visible: VideoSummary[];
  query: string;
  selection: ReadonlySet<string>;
  onShowSkipped: () => void;
  onDelete: (names: string[]) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const banner = useRef<HTMLDivElement>(null);
  const box = useScrollBox(scroller);
  const [bannerHeight, setBannerHeight] = useState(0);

  useEffect(() => {
    const el = banner.current;
    if (!el) return setBannerHeight(0);
    const observer = new ResizeObserver(() => setBannerHeight(el.offsetHeight));
    observer.observe(el);
    return () => observer.disconnect();
  }, [library.skipped.length]);

  if (!library.videos.length) {
    return (
      <div className="page-scroll">
        <EmptyState
          icon="film"
          title="No Videos"
          actions={
            <>
              <Button onClick={() => void reloadLibrary()}>Reload Library</Button>
              {library.skipped.length > 0 && <Button onClick={onShowSkipped}>Show Skipped Files</Button>}
            </>
          }
        >
          {library.skipped.length
            ? `${counted(library.skipped.length, "file was", "files were")} skipped because the names don’t follow the studio-cast-title format.`
            : <>Add videos named studio-cast-title to <code>{library.videosPath}</code>, then reload the library.</>}
        </EmptyState>
      </div>
    );
  }

  const available = Math.max(0, box.width - PADDING * 2);
  const columns = Math.max(1, Math.floor((available + GAP_X) / (CARD_MIN + GAP_X)));
  const cardWidth = Math.min(CARD_MAX, (available - (columns - 1) * GAP_X) / columns);
  const rowHeight = (cardWidth * 9) / 16 + TEXT_HEIGHT + GAP_Y;
  const rows = Math.ceil(visible.length / columns);
  const offset = PADDING + bannerHeight;
  const { start, end } = visibleRange(rows, rowHeight, box.top, box.height, offset);

  return (
    <div ref={scroller} className="page-scroll library__scroll">
      {library.skipped.length > 0 && (
        <div ref={banner} className="library__banner">
          <Callout tone="warning" title={`${counted(library.skipped.length, "file")} skipped`}
            action={<Button size="sm" onClick={onShowSkipped}>Show Files</Button>}>
            Names must be lowercase, without spaces, in the form studio-cast-title.
          </Callout>
        </div>
      )}
      {visible.length === 0 ? (
        <EmptyState icon="search" title={`No Results for “${query.trim()}”`}>
          Check the spelling or try a new search.
        </EmptyState>
      ) : (
        box.width > 0 && (
          <ul
            className="library__grid"
            aria-label="Videos"
            style={{
              gridTemplateColumns: `repeat(${columns}, ${cardWidth}px)`,
              justifyContent: columns === 1 ? "center" : "start",
              gridAutoRows: `${rowHeight - GAP_Y}px`,
              columnGap: GAP_X,
              rowGap: GAP_Y,
              paddingTop: PADDING + start * rowHeight,
              height: Math.max(0, (rows - start) * rowHeight - GAP_Y),
              boxSizing: "content-box",
            }}
          >
            {visible.slice(start * columns, end * columns).map((video) => (
              <VideoCard
                key={video.filename}
                video={video}
                selected={selection.has(video.filename)}
                selection={selection}
                onDelete={onDelete}
              />
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function VideoCard({
  video,
  selected,
  selection,
  onDelete,
}: {
  video: VideoSummary;
  selected: boolean;
  selection: ReadonlySet<string>;
  onDelete: (names: string[]) => void;
}) {
  const inGroup = selected && selection.size > 1;
  return (
    <li className={`card${selected ? " is-selected" : ""}`}>
      <button
        type="button"
        className="card__button"
        aria-pressed={selected}
        aria-label={`${video.title}, ${video.credits}`}
        title={video.filename}
        onClick={() => toggleSelection(video.filename)}
        onContextMenu={(e) =>
          openMenuAt(e, video.title, [
            { label: selected ? "Deselect" : "Select", onSelect: () => toggleSelection(video.filename) },
            { label: "Open Video in New Tab", icon: "external",
              onSelect: () => window.open(`/api/media/video/${encodeURIComponent(video.filename)}`, "_blank", "noopener") },
            { separator: true },
            inGroup
              ? { label: `Delete ${counted(selection.size, "Video")}…`, icon: "trash", destructive: true,
                  onSelect: () => onDelete([...selection]) }
              : { label: `Delete “${video.title}”…`, icon: "trash", destructive: true,
                  onSelect: () => onDelete([video.filename]) },
          ])
        }
      >
        <span className="card__media on-stage" {...hoverPreviewHandlers(video.previewUrl)}>
          <Thumbnail src={video.thumbUrl} />
          <span className="card__badge" aria-hidden="true">
            <Icon name={selected ? "checkCircle" : "circle"} size={22} />
          </span>
        </span>
        <span className="card__text">
          <span className="card__title truncate">{video.title}</span>
          <span className="card__credits truncate">{video.credits}</span>
        </span>
      </button>
      {video.previewUrl && (
        <button
          type="button"
          className="card__preview"
          aria-label={`Preview ${video.title}`}
          title="Preview"
          onClick={() => openPreview(video.previewUrl!, video.title)}
        >
          <Icon name="expand" size={16} />
        </button>
      )}
    </li>
  );
}
