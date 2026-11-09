interface TgpViewProps {
  tgpUrl: string;
}

export default function TgpView({ tgpUrl }: TgpViewProps) {
  return (
    <div style={{ width: "100%", height: "100%", overflow: "auto", display: "flex", justifyContent: "center" }}>
      <img
        src={tgpUrl}
        alt="Video contact sheet"
        style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
      />
    </div>
  );
}
