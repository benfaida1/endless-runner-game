import Phaser from 'phaser';

export default class MenuScene extends Phaser.Scene {
  constructor() {
    super({ key: 'MenuScene' });
  }

  create() {
    const { width, height } = this.scale;

    // Background
    this.add.image(width / 2, height / 2, 'background').setDisplaySize(width, height);

    // Animated clouds
    this.clouds = [];
    const cloudKeys = ['cloud1', 'cloud2'];
    for (let i = 0; i < 5; i++) {
      const key = cloudKeys[i % 2];
      const cloud = this.add.image(
        Phaser.Math.Between(0, width),
        Phaser.Math.Between(50, 250),
        key
      ).setAlpha(0.6);
      this.clouds.push({ sprite: cloud, speed: Phaser.Math.FloatBetween(0.2, 0.5) });
    }

    // Ground strip at bottom
    this.add.tileSprite(width / 2, height - 40, width, 80, 'ground');

    // Decorative robot character on menu
    const robotScale = 2.5;
    const robotX = width / 2;
    const robotY = height * 0.42;
    const robot = this.add.image(robotX, robotY, 'player_run1').setScale(robotScale);

    // Robot idle bounce
    this.tweens.add({
      targets: robot,
      y: robotY - 8,
      duration: 600,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });

    // Alternate run frames for robot on menu
    let runFrame = 0;
    const runFrames = ['player_run1', 'player_run2', 'player_run3', 'player_run4'];
    this.time.addEvent({
      delay: 120,
      loop: true,
      callback: () => {
        runFrame = (runFrame + 1) % runFrames.length;
        robot.setTexture(runFrames[runFrame]);
      }
    });

    // Glow behind robot
    const robotGlow = this.add.graphics();
    robotGlow.fillStyle(0x00ffcc, 0.15);
    robotGlow.fillCircle(robotX, robotY + 10, 60);
    this.children.bringToTop(robot);

    // Title panel
    const panelY = height * 0.15;
    const panel = this.add.graphics();
    panel.fillStyle(0x000000, 0.5);
    panel.fillRoundedRect(width / 2 - 170, panelY - 40, 340, 80, 16);
    panel.lineStyle(2, 0x9900ff, 1);
    panel.strokeRoundedRect(width / 2 - 170, panelY - 40, 340, 80, 16);

    // Title text with neon glow
    this.add.text(width / 2, panelY, 'NEON RUNNER', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '38px',
      fontStyle: 'bold',
      color: '#00ffcc',
      stroke: '#9900ff',
      strokeThickness: 5,
      shadow: {
        offsetX: 0, offsetY: 0,
        color: '#00ffcc',
        blur: 24,
        fill: true,
      }
    }).setOrigin(0.5);

    // Tagline
    this.add.text(width / 2, panelY + 30, 'HOW FAR CAN YOU GO?', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '13px',
      color: '#cc88ff',
      letterSpacing: 2,
    }).setOrigin(0.5);

    // High score display
    const highScore = parseInt(localStorage.getItem('neonRunnerHighScore') || '0', 10);
    const hsPanel = this.add.graphics();
    hsPanel.fillStyle(0x110033, 0.8);
    hsPanel.fillRoundedRect(width / 2 - 120, height * 0.55 - 20, 240, 36, 8);
    this.add.text(width / 2, height * 0.55, `BEST: ${highScore}`, {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '18px',
      color: '#ffdd00',
      stroke: '#884400',
      strokeThickness: 2,
    }).setOrigin(0.5);

    // Play button
    this.createPlayButton(width / 2, height * 0.68);

    // Controls hint
    this.add.text(width / 2, height * 0.80, 'TAP OR PRESS SPACE TO JUMP', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '12px',
      color: '#8866aa',
    }).setOrigin(0.5);

    this.add.text(width / 2, height * 0.84, 'DOUBLE JUMP ALLOWED  |  3 LIVES', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '11px',
      color: '#664488',
    }).setOrigin(0.5);

    // Version
    this.add.text(width - 10, height - 10, 'v1.0', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '10px',
      color: '#443355',
    }).setOrigin(1, 1);

    // Floating neon particles
    this.createMenuParticles();

    // Fade in
    this.cameras.main.fadeIn(400, 0, 0, 0);
  }

  createPlayButton(x, y) {
    const btnW = 220;
    const btnH = 58;

    const btn = this.add.graphics();
    const drawBtn = (hover) => {
      btn.clear();
      const alpha = hover ? 0.95 : 0.85;
      btn.fillStyle(0x9900ff, alpha);
      btn.fillRoundedRect(x - btnW / 2, y - btnH / 2, btnW, btnH, 14);
      btn.lineStyle(3, hover ? 0x00ffcc : 0xcc44ff, 1);
      btn.strokeRoundedRect(x - btnW / 2, y - btnH / 2, btnW, btnH, 14);
      // Inner highlight
      btn.fillStyle(0xffffff, 0.12);
      btn.fillRoundedRect(x - btnW / 2 + 4, y - btnH / 2 + 4, btnW - 8, 18, 8);
    };
    drawBtn(false);

    const btnText = this.add.text(x, y, '▶  PLAY', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '26px',
      fontStyle: 'bold',
      color: '#ffffff',
      stroke: '#440088',
      strokeThickness: 3,
      shadow: { offsetX: 0, offsetY: 2, color: '#000000', blur: 4, fill: true }
    }).setOrigin(0.5);

    // Hit area
    const hitArea = this.add.zone(x, y, btnW, btnH).setInteractive({ useHandCursor: true });

    hitArea.on('pointerover', () => {
      drawBtn(true);
      btnText.setScale(1.05);
    });
    hitArea.on('pointerout', () => {
      drawBtn(false);
      btnText.setScale(1.0);
    });
    hitArea.on('pointerdown', () => {
      this.startGame();
    });

    // Keyboard
    this.input.keyboard.on('keydown-SPACE', () => {
      this.startGame();
    });
    this.input.keyboard.on('keydown-ENTER', () => {
      this.startGame();
    });

    // Pulse animation
    this.tweens.add({
      targets: [btn, btnText],
      alpha: { from: 1, to: 0.7 },
      duration: 900,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  startGame() {
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.scene.start('GameScene');
    });
  }

  createMenuParticles() {
    const { width, height } = this.scale;
    const particles = [];
    const colors = [0x00ffcc, 0xff00ff, 0x9900ff, 0xffdd00, 0x00aaff];

    for (let i = 0; i < 20; i++) {
      const p = this.add.graphics();
      const color = colors[i % colors.length];
      p.fillStyle(color, Phaser.Math.FloatBetween(0.3, 0.9));
      const size = Phaser.Math.Between(1, 4);
      p.fillRect(0, 0, size, size);
      p.x = Phaser.Math.Between(0, width);
      p.y = Phaser.Math.Between(0, height);
      particles.push(p);

      // Float upward
      this.tweens.add({
        targets: p,
        y: p.y - Phaser.Math.Between(80, 200),
        x: p.x + Phaser.Math.Between(-40, 40),
        alpha: 0,
        duration: Phaser.Math.Between(2000, 4000),
        repeat: -1,
        repeatDelay: Phaser.Math.Between(0, 2000),
        ease: 'Linear',
        onRepeat: () => {
          p.x = Phaser.Math.Between(0, width);
          p.y = Phaser.Math.Between(height * 0.5, height);
          p.alpha = Phaser.Math.FloatBetween(0.3, 0.9);
        }
      });
    }
  }

  update() {
    // Scroll clouds
    this.clouds.forEach(({ sprite, speed }) => {
      sprite.x -= speed;
      if (sprite.x < -100) {
        sprite.x = this.scale.width + 100;
        sprite.y = Phaser.Math.Between(50, 250);
      }
    });
  }
}
