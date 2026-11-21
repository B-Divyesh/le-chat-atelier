import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { useVideoConfig } from "remotion";
import {
  ColdOpen,
  Futures,
  GENRE_LEN,
  Genres,
  HowItWorks,
  Outro,
  PromptToWorld,
  Results,
  Story,
  TheLoop,
  Title,
} from "./scenes/Scenes";

export const TRANSITION = 14;

export const LaunchVideo: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence name="Cold open" durationInFrames={Math.round(3.5 * fps)}>
        <ColdOpen />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="Title" durationInFrames={4 * fps}>
        <Title />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="How it works" durationInFrames={7 * fps}>
        <HowItWorks />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={linearTiming({ durationInFrames: TRANSITION + 4 })} />
      <TransitionSeries.Sequence name="Design and draw" durationInFrames={6 * fps}>
        <PromptToWorld />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="The loop" durationInFrames={8 * fps}>
        <TheLoop />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={linearTiming({ durationInFrames: TRANSITION + 4 })} />
      <TransitionSeries.Sequence name="Five genres" durationInFrames={GENRE_LEN * 5}>
        <Genres />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="Imagined futures" durationInFrames={Math.round(5.5 * fps)}>
        <Futures />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="Results" durationInFrames={7 * fps}>
        <Results />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="Story" durationInFrames={Math.round(4.5 * fps)}>
        <Story />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
      <TransitionSeries.Sequence name="Outro" durationInFrames={5 * fps}>
        <Outro />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
