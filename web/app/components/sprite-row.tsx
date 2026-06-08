import Image from "next/image";

export function SpriteRow({ filenames, size = 24 }: { filenames: string[]; size?: number }) {
  if (!filenames || filenames.length === 0) return null;

  return (
    <span className="inline-flex items-center gap-1">
      {filenames.map((fn) => (
        <Image
          key={fn}
          src={`/data/images/sprites/${fn}`}
          alt={fn.replace(".png", "")}
          width={size}
          height={size}
          className="pixelated"
          unoptimized
        />
      ))}
    </span>
  );
}
