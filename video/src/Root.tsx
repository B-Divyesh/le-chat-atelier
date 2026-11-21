import React from "react";
import { Composition } from "remotion";
import { LaunchVideo } from "./LaunchVideo";

// 30 fps: scenes 105+120+210+180+240+330+165+210+135+150 = 1845 frames, minus 7×14 + 2×18 transition overlaps = 1711
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="Launch" component={LaunchVideo} durationInFrames={1711} fps={30} width={1920} height={1080} />
    </>
  );
};
