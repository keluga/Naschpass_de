import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BODY, C, HEAD, SAFE } from "../theme";
import { Scene } from "./types";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Frame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill
    style={{
      paddingLeft: SAFE.left,
      paddingRight: SAFE.right,
      paddingTop: SAFE.top,
      paddingBottom: SAFE.bottom,
      justifyContent: "center",
      alignItems: "flex-start",
      flexDirection: "column",
      gap: 36,
    }}
  >
    {children}
  </AbsoluteFill>
);

const useFade = (start: number, dur = 10) => {
  const f = useCurrentFrame();
  return {
    opacity: interpolate(f, [start, start + dur], [0, 1], clamp),
    transform: `translateY(${interpolate(f, [start, start + dur], [30, 0], { ...clamp, easing: Easing.out(Easing.cubic) })}px)`,
  };
};

const Sub: React.FC<{ text: string; start: number; color?: string }> = ({ text, start, color = C.yellow }) => (
  <div style={{ ...useFade(start), fontFamily: BODY, fontWeight: 700, fontSize: 62, color, lineHeight: 1.25 }}>
    {text}
  </div>
);

// Neutraler Schoko-Riegel ohne Marke oder Logo
const Bar: React.FC<{ start: number }> = ({ start }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - start, fps, config: { damping: 14 } });
  const finger = (x: number) => (
    <g transform={`translate(${x},0)`}>
      <rect x="0" y="0" width="560" height="120" rx="40" fill="#4A2612" />
      <rect x="18" y="16" width="524" height="40" rx="18" fill="#D98E32" />
      <rect x="18" y="62" width="524" height="40" rx="18" fill="#E8C07A" />
      <rect x="0" y="0" width="560" height="120" rx="40" fill="none" stroke="#2B140A" strokeWidth="6" />
    </g>
  );
  return (
    <svg
      width="840"
      height="384"
      viewBox="0 0 700 320"
      style={{
        transform: `translateY(${interpolate(s, [0, 1], [500, 0])}px) rotate(${interpolate(s, [0, 1], [-18, -6])}deg)`,
        opacity: interpolate(f, [start, start + 6], [0, 1], clamp),
      }}
    >
      <g transform="translate(40,30)">{finger(0)}</g>
      <g transform="translate(90,170)">{finger(0)}</g>
    </svg>
  );
};

const YearRoll: React.FC<Extract<Scene, { type: "yearRoll" }>> = ({ headline, from, to, sub }) => {
  const f = useCurrentFrame();
  const year = Math.round(interpolate(f, [8, 52], [from, to], { ...clamp, easing: Easing.out(Easing.cubic) }));
  const pop = interpolate(f, [52, 58, 66], [1, 1.12, 1], clamp);
  return (
    <Frame>
      <div style={{ ...useFade(0, 8), fontFamily: HEAD, fontSize: 124, color: C.text, lineHeight: 1.05, textTransform: "uppercase" }}>
        {headline}
      </div>
      <div style={{ fontFamily: HEAD, fontSize: 430, color: C.yellow, lineHeight: 1, transform: `scale(${pop})`, transformOrigin: "left center" }}>
        {year}
      </div>
      {sub ? <Sub text={sub} start={56} /> : null}
    </Frame>
  );
};

const BigWord: React.FC<Extract<Scene, { type: "bigWord" }>> = ({ word, sub, bar }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 9, mass: 0.8 } });
  const shake = f < 12 ? Math.sin(f * 2.4) * (12 - f) : 0;
  return (
    <Frame>
      <div
        style={{
          fontFamily: HEAD,
          fontSize: 310,
          color: C.pink,
          lineHeight: 0.95,
          transform: `scale(${interpolate(s, [0, 1], [2.4, 1])}) translateX(${shake}px)`,
          transformOrigin: "left center",
        }}
      >
        {word}
      </div>
      {sub ? <Sub text={sub} start={14} /> : null}
      {bar ? <Bar start={10} /> : null}
    </Frame>
  );
};

const Swap: React.FC<Extract<Scene, { type: "swap" }>> = ({ label, oldWord, newWord, sub }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const strike = interpolate(f, [14, 28], [0, 100], clamp);
  const drop = interpolate(f, [32, 50], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) });
  const s = spring({ frame: f - 44, fps, config: { damping: 10 } });
  return (
    <Frame>
      <div style={{ ...useFade(0, 8), fontFamily: HEAD, fontSize: 150, color: C.yellow }}>{label}</div>
      <div style={{ position: "relative", height: 320, width: "100%" }}>
        <div
          style={{
            position: "absolute",
            fontFamily: HEAD,
            fontSize: 290,
            color: C.text,
            lineHeight: 1,
            opacity: 1 - drop,
            transform: `translateY(${drop * 420}px) rotate(${drop * 16}deg)`,
          }}
        >
          {oldWord}
          <div style={{ position: "absolute", left: 0, top: "48%", height: 22, width: `${strike}%`, background: C.pink, borderRadius: 11 }} />
        </div>
        <div
          style={{
            position: "absolute",
            fontFamily: HEAD,
            fontSize: 290,
            color: C.mint,
            lineHeight: 1,
            opacity: f >= 44 ? 1 : 0,
            transform: `scale(${interpolate(s, [0, 1], [0.3, 1])})`,
            transformOrigin: "left center",
          }}
        >
          {newWord}
        </div>
      </div>
      <Sub text={sub} start={56} />
    </Frame>
  );
};

const Statement: React.FC<Extract<Scene, { type: "statement" }>> = ({ lines, accent }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Frame>
      {lines.map((line, i) => {
        const s = spring({ frame: f - i * 18, fps, config: { damping: 12 } });
        return (
          <div
            key={line}
            style={{
              fontFamily: HEAD,
              fontSize: 185,
              lineHeight: 1,
              textTransform: "uppercase",
              color: i === accent ? C.pink : C.text,
              opacity: interpolate(s, [0, 0.3], [0, 1], clamp),
              transform: `translateY(${interpolate(s, [0, 1], [120, 0])}px)`,
            }}
          >
            {line}
          </div>
        );
      })}
    </Frame>
  );
};

const Pill: React.FC<{ text: string; start: number; color: string }> = ({ text, start, color }) => {
  const f = useCurrentFrame();
  const pulse = 1 + 0.04 * Math.sin((f - start) / 5);
  return (
    <div
      style={{
        ...useFade(start, 8),
        fontFamily: HEAD,
        fontSize: 80,
        color: C.bg,
        background: color,
        padding: "14px 44px",
        borderRadius: 999,
        scale: f > start + 10 ? String(pulse) : "1",
      }}
    >
      {text}
    </div>
  );
};

const Question: React.FC<Extract<Scene, { type: "question" }>> = ({ lead, word, options, cta }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - 10, fps, config: { damping: 9 } });
  return (
    <Frame>
      <div style={{ ...useFade(0, 8), fontFamily: HEAD, fontSize: 124, color: C.text, lineHeight: 1.05, textTransform: "uppercase" }}>
        {lead}
      </div>
      <div
        style={{
          fontFamily: HEAD,
          fontSize: 270,
          color: C.pink,
          lineHeight: 1,
          transform: `scale(${interpolate(s, [0, 1], [0.4, 1])})`,
          transformOrigin: "left center",
        }}
      >
        {word}
      </div>
      <div style={{ display: "flex", gap: 30, alignItems: "center" }}>
        <Pill text={options[0]} start={26} color={C.yellow} />
        <div style={{ ...useFade(30), fontFamily: BODY, fontWeight: 800, fontSize: 48, color: C.text }}>oder</div>
        <Pill text={options[1]} start={34} color={C.mint} />
      </div>
      <Sub text={cta} start={46} color={C.text} />
    </Frame>
  );
};

export const SceneView: React.FC<{ scene: Scene }> = ({ scene }) => {
  switch (scene.type) {
    case "yearRoll":
      return <YearRoll {...scene} />;
    case "bigWord":
      return <BigWord {...scene} />;
    case "swap":
      return <Swap {...scene} />;
    case "statement":
      return <Statement {...scene} />;
    case "question":
      return <Question {...scene} />;
  }
};
