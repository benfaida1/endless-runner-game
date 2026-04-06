import Phaser from 'phaser';
import BootScene from './scenes/BootScene.js';
import MenuScene from './scenes/MenuScene.js';
import GameScene from './scenes/GameScene.js';
import GameOverScene from './scenes/GameOverScene.js';

// Hide the HTML loading screen once JS is loaded
window.addEventListener('load', () => {
  const loadingScreen = document.getElementById('loading-screen');
  if (loadingScreen) {
    loadingScreen.style.transition = 'opacity 0.5s ease';
    loadingScreen.style.opacity = '0';
    setTimeout(() => {
      loadingScreen.style.display = 'none';
    }, 500);
  }
});

const GAME_WIDTH = 375;
const GAME_HEIGHT = 667;

const config = {
  type: Phaser.AUTO,
  width: GAME_WIDTH,
  height: GAME_HEIGHT,
  parent: 'game-container',
  backgroundColor: '#1a0533',
  physics: {
    default: 'arcade',
    arcade: {
      gravity: { y: 1800 },
      debug: false,
    }
  },
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
    width: GAME_WIDTH,
    height: GAME_HEIGHT,
  },
  scene: [BootScene, MenuScene, GameScene, GameOverScene],
  audio: {
    disableWebAudio: false,
  },
  render: {
    antialias: false,
    pixelArt: true,
    roundPixels: true,
  },
  input: {
    activePointers: 3,
  },
};

const game = new Phaser.Game(config);

export default game;
