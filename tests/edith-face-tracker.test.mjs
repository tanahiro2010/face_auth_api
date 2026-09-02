import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(
  new URL("../static/edith-face-tracker.html", import.meta.url),
  "utf8"
);

function loadPostTrackFace({ postFaceImage }) {
  const start = html.indexOf("    async function postTrackFace(");
  const end = html.indexOf("\n    function applyIdentity", start);
  assert.notEqual(start, -1, "postTrackFace should exist in the tracker HTML");
  assert.notEqual(end, -1, "postTrackFace should end before applyIdentity");

  const source = html.slice(start, end);
  return new Function(
    "canvasToBlob",
    "postFaceImage",
    `${source}\nreturn postTrackFace;`
  )(
    async (canvas) => ({ canvas }),
    postFaceImage
  );
}

function makeTrack() {
  return {
    alignedFace: {
      apiCanvas: { id: "raw" },
      apiWideCanvas: { id: "wide" },
      apiAlignedCanvas: { id: "aligned" },
      apiWideAlignedCanvas: { id: "wide-aligned" },
    },
  };
}

test("identify retries another crop when the first crop does not match", async () => {
  const triedVariants = [];
  const postTrackFace = loadPostTrackFace({
    postFaceImage: async (_path, _blob, fields) => {
      triedVariants.push(fields.crop_variant);
      if (fields.crop_variant === "raw") {
        const error = new Error("similarity below threshold");
        error.status = 404;
        throw error;
      }
      return { person: { name: "tanaka" }, similarity: 0.72 };
    },
  });

  const result = await postTrackFace("/faces/identify", makeTrack());

  assert.equal(result.person.name, "tanaka");
  assert.deepEqual(triedVariants, ["raw", "wide"]);
});

test("register still retries a crop that contains no detectable face", async () => {
  const triedVariants = [];
  const postTrackFace = loadPostTrackFace({
    postFaceImage: async (_path, _blob, fields) => {
      triedVariants.push(fields.crop_variant);
      if (fields.crop_variant === "raw") {
        const error = new Error("no face");
        error.status = 422;
        throw error;
      }
      return { name: "tanaka" };
    },
  });

  const result = await postTrackFace("/faces/register", makeTrack());

  assert.equal(result.name, "tanaka");
  assert.deepEqual(triedVariants, ["raw", "wide"]);
});
