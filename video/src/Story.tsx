import React from "react";
import { AbsoluteFill, Series, interpolate, useCurrentFrame } from "remotion";
import { SceneView } from "./scenes/Scenes";
import { StoryProps } from "./scenes/types";
import { BODY, C, HEAD } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Kurzer Lichtblitz beim Szenenwechsel
const Flash: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.text, opacity: interpolate(f, [0, 4], [0.35, 0], clamp) }} />;
};

// Retro-Look: Scanlines, Vignette, leichtes Flackern, PLAY-Anzeige wie beim Videorekorder
const Retro: React.FC = () => {
  const f = useCurrentFrame();
  const flicker = 0.06 + 0.03 * Math.abs(Math.sin(f * 1.7));
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          backgroundImage: "repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 2px, transparent 2px, transparent 5px)",
          opacity: 0.55,
        }}
      />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.65) 100%)" }} />
      <AbsoluteFill style={{ background: C.text, opacity: flicker * 0.25 }} />
      <div
        style={{
          position: "absolute",
          top: 170,
          left: 90,
          fontFamily: BODY,
          fontWeight: 800,
          fontSize: 40,
          letterSpacing: 4,
          color: C.text,
          opacity: Math.floor(f / 15) % 2 === 0 ? 0.9 : 0.35,
        }}
      >
        ▶ PLAY
      </div>
    </AbsoluteFill>
  );
};

const Sprinkles: React.FC = () => {
  const f = useCurrentFrame();
  const items = [
    [930, 520, 30, C.pink], [960, 820, -20, C.yellow], [905, 1150, 60, C.mint],
    [60, 1480, 15, C.yellow], [980, 1420, -45, C.pink], [40, 300, 70, C.mint],
  ] as const;
  return (
    <AbsoluteFill>
      {items.map(([x, y, r, col], i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: x,
            top: y + Math.sin((f + i * 20) / 18) * 10,
            width: 60,
            height: 16,
            borderRadius: 8,
            background: col,
            transform: `rotate(${r + f * 0.3}deg)`,
            opacity: 0.85,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

export const Story: React.FC<StoryProps> = ({ scenes, handle, retro }) => {
  return (
    <AbsoluteFill style={{ background: `linear-gradient(170deg, ${C.bg2} 0%, ${C.bg} 60%)` }}>
      <Sprinkles />
      <Series>
        {scenes.map((scene, i) => (
          <Series.Sequence key={i} durationInFrames={scene.frames}>
            <SceneView scene={scene} />
            {i > 0 ? <Flash /> : null}
          </Series.Sequence>
        ))}
      </Series>
      {retro ? <Retro /> : null}
      <div style={{ position: "absolute", top: 170, right: 150, fontFamily: HEAD, fontSize: 40, color: C.yellow, letterSpacing: 2 }}>
        {handle}
      </div>
    </AbsoluteFill>
  );
};
