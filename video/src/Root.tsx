import React from "react";
import { Composition } from "remotion";
import "./theme";
import { Story } from "./Story";
import { StoryProps } from "./scenes/types";
import { raider } from "./stories/raider";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Raider"
      component={Story}
      fps={30}
      width={1080}
      height={1920}
      durationInFrames={1}
      defaultProps={raider}
      calculateMetadata={({ props }: { props: StoryProps }) => ({
        durationInFrames: props.scenes.reduce((sum, s) => sum + s.frames, 0),
      })}
    />
  );
};
