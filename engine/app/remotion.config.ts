import {Config} from '@remotion/cli/config';
// three.js needs a real GPU context: ANGLE renders WebGL through Metal on Apple silicon.
Config.setChromiumOpenGlRenderer('angle');
Config.setVideoImageFormat('jpeg');
Config.setConcurrency(2); // fanless M5: keep the load moderate
// Remotion 4.0.290's own downloader fails on Node 26; use the same Chrome for Testing build fetched with curl.
Config.setBrowserExecutable(`${process.env.HOME}/kathakaar-lab/tools/chrome-headless-shell-mac-arm64/chrome-headless-shell`);
