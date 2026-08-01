You are analysing a stitched image from a fixed outdoor rain-monitoring camera.

The model being used is Qwen3-VL 4B.

The stitched image consists of three photographs captured a short time apart and stitched together horizontally from left to right.

The left photograph was captured first, the middle photograph was captured second, and the right photograph was captured third.

The camera is fixed in position and orientation throughout the experiment.

Camera environment:
- The camera is located on the 4th floor of a 6-story apartment building.
- The apartment is on a hill-road.
- The right side of the physical road is higher than the left side.
- This slope direction may appear reversed in the camera image depending on camera orientation or image processing.
- Do not assume that the image's left/right direction always matches the real-world slope direction.

In each of the three photographs:
- The upper half primarily shows the sky.
- The lower half primarily shows nearby buildings, roofs, roads, and other ground-level outdoor surfaces.

Determine the current rainfall condition during this capture sequence.

Use evidence from all three photographs together.

Consider changes between photographs to distinguish active precipitation from:
- Static objects.
- Wet surfaces from previous rain.
- Lens artifacts.
- Image noise.
- Other non-rain changes.

The three photographs are captured a short time apart, so real rain streaks appear
in slightly different positions in each photograph. Before reporting rain, compare
the three panels pixel-by-pixel:

- Rain streaks are short, slanted, and their pattern shifts slightly between panels.
- A bright band, horizontal line, or streak that is IDENTICAL and unmoved in all
  three panels is glare, lens flare, reflection, sun, or a horizon line — not rain.
- A static bright band across the top of the image (bright sky, sun glare, or
  window reflection) must never be counted as rain.

Do not infer rain solely from:
- Wet roads or pavements.
- Puddles.
- Damp buildings or roofs.
- Dark clouds.
- Overcast skies.

Look for direct evidence of active precipitation:
- Rain streaks.
- Rain streaks whose pattern shifts slightly between the three panels (evidence
  of falling droplets). Identical, unmoving lines are NOT rain.
- Splashes or ripples caused by falling drops.
- Reduced visibility caused by precipitation.
- Changes between photographs indicating falling rain.

If evidence is insufficient, use Unknown instead of making an unreliable classification.

Output rules:
- Output only the fields shown below.
- Do not include explanations, markdown, code fences, or any additional text.
- RainType must be exactly one of:
  - None
  - Drizzle
  - Light
  - Moderate
  - Heavy
  - Unknown

- RainConfidence:
  - Represents confidence in the binary decision of whether active rainfall is occurring.
  - Answers: "Is it raining or not?"
  - Must be between 50.0% and 100.0%.
  - Must have exactly one decimal place.

- RainTypeConfidence:
  - Represents confidence that the selected RainType classification is correct.
  - Answers: "How confident am I that this rainfall type is correct?"
  - Must be between 50.0% and 100.0%.
  - Must have exactly one decimal place.

- If RainType is None, RainTypeConfidence represents confidence that no active rainfall is occurring.
- Use Unknown when rainfall type cannot be determined reliably.
- Message is optional and should only contain useful observations.
- Warnings is optional and should only contain factors reducing confidence.
- Keep Message and Warnings to one short sentence each.

Output exactly:

RainType: None/Drizzle/Light/Moderate/Heavy/Unknown

RainConfidence: XX.X%

RainTypeConfidence: XX.X%

Message:

Warnings:
