import Phaser from 'phaser';

export default class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  create() {
    this.createBackgroundTexture();
    this.createGroundTexture();
    this.createPlayerTextures();
    this.createObstacleTextures();
    this.createCloudTexture();
    this.createParticleTextures();
    this.createUITextures();
    this.showSplash();
  }

  // ─── Background ────────────────────────────────────────────────────────────

  createBackgroundTexture() {
    const w = 375;
    const h = 667;
    const key = 'background';

    const gfx = this.make.graphics({ x: 0, y: 0, add: false });

    // Night sky gradient (top → purple, bottom → dark blue)
    const steps = 20;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      const r = Phaser.Math.Linear(0x1a, 0x0d, t);
      const g = Phaser.Math.Linear(0x05, 0x1b, t);
      const b = Phaser.Math.Linear(0x33, 0x4b, t);
      const color = (Math.round(r) << 16) | (Math.round(g) << 8) | Math.round(b);
      gfx.fillStyle(color, 1);
      const y = Math.floor((i / steps) * h);
      const nextY = Math.floor(((i + 1) / steps) * h);
      gfx.fillRect(0, y, w, nextY - y);
    }

    // Stars
    const starData = [
      [30,20],[80,60],[150,15],[200,45],[260,30],[320,55],[50,100],[110,80],
      [170,95],[240,70],[300,90],[360,40],[20,130],[90,150],[160,120],[220,140],
      [280,110],[340,160],[60,180],[130,200],[190,170],[250,190],[310,175],[10,220],
      [75,240],[145,215],[205,235],[265,210],[325,230],[370,200],[40,260],[100,280],
      [165,255],[225,275],[285,250],[345,270],
    ];
    starData.forEach(([sx, sy]) => {
      const size = Phaser.Math.Between(1, 2);
      const brightness = Phaser.Math.FloatBetween(0.5, 1.0);
      gfx.fillStyle(0xffffff, brightness);
      gfx.fillRect(sx, sy, size, size);
    });

    // Distant mountains/hills silhouette
    gfx.fillStyle(0x150428, 1);
    gfx.fillTriangle(0, 360, 80, 260, 160, 360);
    gfx.fillTriangle(100, 360, 200, 220, 300, 360);
    gfx.fillTriangle(240, 360, 330, 250, 420, 360);
    gfx.fillRect(0, 355, w, 15);

    gfx.generateTexture(key, w, h);
    gfx.destroy();
  }

  // ─── Ground ─────────────────────────────────────────────────────────────────

  createGroundTexture() {
    // Tiling ground strip 375×80
    const gw = 375;
    const gh = 80;
    const gfx = this.make.graphics({ x: 0, y: 0, add: false });

    // Base dirt/ground color
    gfx.fillStyle(0x2a1045, 1);
    gfx.fillRect(0, 0, gw, gh);

    // Top neon line
    gfx.fillStyle(0x9900ff, 1);
    gfx.fillRect(0, 0, gw, 3);

    // Secondary glow line
    gfx.fillStyle(0xcc44ff, 0.5);
    gfx.fillRect(0, 3, gw, 2);

    // Horizontal grid lines
    gfx.fillStyle(0x4a1080, 0.6);
    for (let y = 15; y < gh; y += 15) {
      gfx.fillRect(0, y, gw, 1);
    }

    // Vertical grid lines (perspective-ish)
    gfx.fillStyle(0x4a1080, 0.4);
    for (let x = 0; x < gw; x += 30) {
      gfx.fillRect(x, 0, 1, gh);
    }

    gfx.generateTexture('ground', gw, gh);
    gfx.destroy();
  }

  // ─── Player ─────────────────────────────────────────────────────────────────

  createPlayerTextures() {
    this.createRobotRun();
    this.createRobotJump();
    this.createRobotHurt();
  }

  drawRobotBase(gfx, offsetY = 0) {
    const oy = offsetY;
    // Body
    gfx.fillStyle(0x00ffcc, 1);
    gfx.fillRect(12, 8 + oy, 24, 22); // torso
    // Body highlight
    gfx.fillStyle(0x88ffee, 1);
    gfx.fillRect(14, 10 + oy, 8, 6);
    // Head
    gfx.fillStyle(0x00ddaa, 1);
    gfx.fillRect(14, 0 + oy, 20, 16);
    // Visor / eye
    gfx.fillStyle(0xff00ff, 1);
    gfx.fillRect(17, 4 + oy, 14, 6);
    gfx.fillStyle(0xffffff, 0.8);
    gfx.fillRect(18, 5 + oy, 5, 4);
    // Antenna
    gfx.fillStyle(0xff00ff, 1);
    gfx.fillRect(22, -4 + oy, 3, 5);
    gfx.fillStyle(0xffffff, 1);
    gfx.fillRect(22, -6 + oy, 3, 3);
    // Arms
    gfx.fillStyle(0x00bbaa, 1);
    gfx.fillRect(4, 10 + oy, 8, 6);   // left arm
    gfx.fillRect(36, 10 + oy, 8, 6);  // right arm
    // Chest detail
    gfx.fillStyle(0x00ffff, 0.7);
    gfx.fillRect(19, 16 + oy, 10, 3);
    gfx.fillRect(19, 21 + oy, 10, 3);
  }

  createRobotRun() {
    // Frame 1 – left leg forward
    const g1 = this.make.graphics({ add: false });
    this.drawRobotBase(g1);
    // Legs
    g1.fillStyle(0x009977, 1);
    g1.fillRect(14, 30, 8, 14); // left leg back
    g1.fillRect(26, 30, 8, 12); // right leg front
    // Feet
    g1.fillStyle(0xff00ff, 1);
    g1.fillRect(12, 44, 10, 4);
    g1.fillRect(26, 42, 10, 4);
    g1.generateTexture('player_run1', 48, 50);
    g1.destroy();

    // Frame 2 – right leg forward
    const g2 = this.make.graphics({ add: false });
    this.drawRobotBase(g2);
    g2.fillStyle(0x009977, 1);
    g2.fillRect(14, 30, 8, 12);
    g2.fillRect(26, 30, 8, 14);
    g2.fillStyle(0xff00ff, 1);
    g2.fillRect(14, 42, 10, 4);
    g2.fillRect(24, 44, 10, 4);
    g2.generateTexture('player_run2', 48, 50);
    g2.destroy();

    // Frame 3 – mid stride
    const g3 = this.make.graphics({ add: false });
    this.drawRobotBase(g3, -2);
    g3.fillStyle(0x009977, 1);
    g3.fillRect(14, 30, 8, 13);
    g3.fillRect(26, 30, 8, 13);
    g3.fillStyle(0xff00ff, 1);
    g3.fillRect(13, 43, 10, 4);
    g3.fillRect(25, 43, 10, 4);
    g3.generateTexture('player_run3', 48, 50);
    g3.destroy();

    // Frame 4 – bounce up
    const g4 = this.make.graphics({ add: false });
    this.drawRobotBase(g4, -4);
    g4.fillStyle(0x009977, 1);
    g4.fillRect(14, 30, 8, 15);
    g4.fillRect(26, 30, 8, 15);
    g4.fillStyle(0xff00ff, 1);
    g4.fillRect(13, 45, 10, 4);
    g4.fillRect(25, 45, 10, 4);
    g4.generateTexture('player_run4', 48, 50);
    g4.destroy();
  }

  createRobotJump() {
    const g = this.make.graphics({ add: false });
    this.drawRobotBase(g, -3);
    // Legs tucked up
    g.fillStyle(0x009977, 1);
    g.fillRect(12, 30, 9, 8);
    g.fillRect(27, 30, 9, 8);
    g.fillStyle(0xff00ff, 1);
    g.fillRect(10, 36, 12, 4);
    g.fillRect(26, 36, 12, 4);
    // Jump glow
    g.fillStyle(0x00ffff, 0.3);
    g.fillCircle(24, 32, 14);
    g.generateTexture('player_jump', 48, 50);
    g.destroy();
  }

  createRobotHurt() {
    const g = this.make.graphics({ add: false });
    // Red tint version
    g.fillStyle(0xff3333, 1);
    g.fillRect(12, 8, 24, 22);
    g.fillStyle(0xff6666, 1);
    g.fillRect(14, 10, 8, 6);
    g.fillStyle(0xdd1111, 1);
    g.fillRect(14, 0, 20, 16);
    g.fillStyle(0xffffff, 1);
    g.fillRect(17, 4, 14, 6);
    g.fillStyle(0xff0000, 1);
    g.fillRect(22, -4, 3, 5);
    g.fillRect(4, 10, 8, 6);
    g.fillRect(36, 10, 8, 6);
    g.fillStyle(0xaa0000, 1);
    g.fillRect(14, 30, 8, 14);
    g.fillRect(26, 30, 8, 12);
    g.fillStyle(0xff2222, 1);
    g.fillRect(12, 44, 10, 4);
    g.fillRect(26, 42, 10, 4);
    g.generateTexture('player_hurt', 48, 50);
    g.destroy();
  }

  // ─── Obstacles ──────────────────────────────────────────────────────────────

  createObstacleTextures() {
    this.createRockTexture();
    this.createBirdTexture();
    this.createBirdTexture2();
  }

  createRockTexture() {
    const g = this.make.graphics({ add: false });
    // Main rock shape
    g.fillStyle(0x553366, 1);
    g.fillRect(4, 20, 36, 28);
    g.fillRect(10, 12, 28, 12);
    g.fillRect(16, 6, 18, 8);
    // Highlights
    g.fillStyle(0x774488, 1);
    g.fillRect(6, 22, 10, 8);
    g.fillRect(12, 14, 8, 6);
    // Neon edge glow
    g.fillStyle(0xaa44ff, 0.8);
    g.fillRect(4, 20, 2, 28);
    g.fillRect(38, 22, 2, 26);
    g.fillRect(10, 12, 2, 10);
    // Shadow
    g.fillStyle(0x110022, 0.6);
    g.fillRect(8, 46, 32, 4);
    g.generateTexture('rock', 48, 52);
    g.destroy();
  }

  createBirdTexture() {
    // Bird frame 1 – wings up
    const g = this.make.graphics({ add: false });
    // Body
    g.fillStyle(0xff6600, 1);
    g.fillRect(16, 14, 20, 12);
    // Head
    g.fillStyle(0xff8833, 1);
    g.fillRect(30, 10, 12, 10);
    // Beak
    g.fillStyle(0xffcc00, 1);
    g.fillRect(40, 13, 8, 4);
    // Eye
    g.fillStyle(0x000000, 1);
    g.fillRect(36, 11, 3, 3);
    g.fillStyle(0xffffff, 1);
    g.fillRect(37, 11, 1, 1);
    // Wings up
    g.fillStyle(0xff4400, 1);
    g.fillRect(8, 4, 14, 12);   // left wing up
    g.fillRect(30, 4, 14, 12);  // right wing up
    // Wing tips
    g.fillStyle(0xff2200, 1);
    g.fillRect(4, 0, 8, 6);
    g.fillRect(38, 0, 8, 6);
    // Tail
    g.fillStyle(0xff4400, 1);
    g.fillRect(8, 16, 10, 6);
    g.fillRect(10, 20, 6, 8);
    // Neon glow outline
    g.fillStyle(0xff6600, 0.3);
    g.fillRect(2, 2, 52, 30);
    g.generateTexture('bird1', 52, 32);
    g.destroy();
  }

  createBirdTexture2() {
    // Bird frame 2 – wings down
    const g = this.make.graphics({ add: false });
    g.fillStyle(0xff6600, 1);
    g.fillRect(16, 10, 20, 12);
    g.fillStyle(0xff8833, 1);
    g.fillRect(30, 6, 12, 10);
    g.fillStyle(0xffcc00, 1);
    g.fillRect(40, 9, 8, 4);
    g.fillStyle(0x000000, 1);
    g.fillRect(36, 7, 3, 3);
    g.fillStyle(0xffffff, 1);
    g.fillRect(37, 7, 1, 1);
    // Wings down
    g.fillStyle(0xff4400, 1);
    g.fillRect(6, 16, 14, 10);  // left wing down
    g.fillRect(32, 16, 14, 10); // right wing down
    g.fillStyle(0xff2200, 1);
    g.fillRect(4, 22, 8, 6);
    g.fillRect(40, 22, 8, 6);
    g.fillStyle(0xff4400, 1);
    g.fillRect(8, 14, 10, 6);
    g.fillRect(10, 18, 6, 8);
    g.generateTexture('bird2', 52, 32);
    g.destroy();
  }

  // ─── Cloud ──────────────────────────────────────────────────────────────────

  createCloudTexture() {
    // Cloud 1
    const g1 = this.make.graphics({ add: false });
    g1.fillStyle(0x3311aa, 0.7);
    g1.fillCircle(30, 24, 20);
    g1.fillCircle(50, 20, 16);
    g1.fillCircle(14, 26, 14);
    g1.fillCircle(64, 26, 12);
    g1.fillStyle(0x4422cc, 0.4);
    g1.fillCircle(32, 22, 18);
    g1.fillCircle(50, 18, 14);
    g1.generateTexture('cloud1', 80, 42);
    g1.destroy();

    // Cloud 2 (wider)
    const g2 = this.make.graphics({ add: false });
    g2.fillStyle(0x220066, 0.6);
    g2.fillCircle(28, 20, 18);
    g2.fillCircle(48, 16, 20);
    g2.fillCircle(70, 20, 16);
    g2.fillCircle(90, 22, 14);
    g2.fillCircle(10, 22, 10);
    g2.fillStyle(0x331188, 0.3);
    g2.fillCircle(50, 18, 30);
    g2.generateTexture('cloud2', 110, 38);
    g2.destroy();
  }

  // ─── Particles ──────────────────────────────────────────────────────────────

  createParticleTextures() {
    // Spark particle
    const g1 = this.make.graphics({ add: false });
    g1.fillStyle(0xffff00, 1);
    g1.fillRect(0, 0, 4, 4);
    g1.generateTexture('spark', 4, 4);
    g1.destroy();

    // Star burst particle
    const g2 = this.make.graphics({ add: false });
    g2.fillStyle(0xff00ff, 1);
    g2.fillRect(2, 0, 4, 8);
    g2.fillRect(0, 2, 8, 4);
    g2.generateTexture('star_particle', 8, 8);
    g2.destroy();

    // Neon dot particle
    const g3 = this.make.graphics({ add: false });
    g3.fillStyle(0x00ffcc, 1);
    g3.fillCircle(3, 3, 3);
    g3.generateTexture('neon_dot', 6, 6);
    g3.destroy();

    // Score pop particle background
    const g4 = this.make.graphics({ add: false });
    g4.fillStyle(0xffffff, 1);
    g4.fillCircle(2, 2, 2);
    g4.generateTexture('white_dot', 4, 4);
    g4.destroy();
  }

  // ─── UI Textures ────────────────────────────────────────────────────────────

  createUITextures() {
    this.createHeartTexture();
    this.createButtonTexture();
    this.createShieldTexture();
    this.createCoinTexture();
  }

  createHeartTexture() {
    // Full heart
    const g1 = this.make.graphics({ add: false });
    g1.fillStyle(0xff2255, 1);
    g1.fillCircle(7, 6, 6);
    g1.fillCircle(17, 6, 6);
    g1.fillTriangle(0, 8, 24, 8, 12, 22);
    g1.fillStyle(0xff6688, 0.7);
    g1.fillCircle(5, 4, 3);
    g1.generateTexture('heart_full', 24, 24);
    g1.destroy();

    // Empty heart
    const g2 = this.make.graphics({ add: false });
    g2.fillStyle(0x441133, 1);
    g2.fillCircle(7, 6, 6);
    g2.fillCircle(17, 6, 6);
    g2.fillTriangle(0, 8, 24, 8, 12, 22);
    g2.fillStyle(0x661144, 0.5);
    g2.fillCircle(5, 4, 3);
    g2.generateTexture('heart_empty', 24, 24);
    g2.destroy();
  }

  createButtonTexture() {
    // Jump button for mobile
    const g = this.make.graphics({ add: false });
    g.fillStyle(0x9900ff, 0.4);
    g.fillCircle(50, 50, 48);
    g.fillStyle(0xcc44ff, 0.6);
    g.fillCircle(50, 50, 40);
    g.fillStyle(0x00ffcc, 0.9);
    // Arrow up shape
    g.fillTriangle(50, 15, 25, 45, 75, 45);
    g.fillRect(38, 45, 24, 22);
    g.generateTexture('jump_button', 100, 100);
    g.destroy();
  }

  createShieldTexture() {
    const g = this.make.graphics({ add: false });
    g.fillStyle(0x0088ff, 0.3);
    g.fillCircle(24, 24, 22);
    g.fillStyle(0x00aaff, 0.6);
    g.fillCircle(24, 24, 18);
    g.fillStyle(0x44ccff, 0.4);
    g.fillCircle(20, 18, 8);
    g.generateTexture('shield', 48, 48);
    g.destroy();
  }

  createCoinTexture() {
    const g = this.make.graphics({ add: false });
    g.fillStyle(0xffdd00, 1);
    g.fillCircle(10, 10, 10);
    g.fillStyle(0xffff88, 0.8);
    g.fillCircle(8, 8, 5);
    g.fillStyle(0xaa8800, 0.5);
    g.fillCircle(10, 10, 10);
    g.fillStyle(0xffdd00, 1);
    g.fillCircle(10, 10, 8);
    g.generateTexture('coin', 20, 20);
    g.destroy();
  }

  // ─── Splash screen ──────────────────────────────────────────────────────────

  showSplash() {
    const { width, height } = this.scale;

    // Background
    this.add.image(width / 2, height / 2, 'background').setDisplaySize(width, height);

    // Title glow effect
    const titleBg = this.add.graphics();
    titleBg.fillStyle(0x9900ff, 0.3);
    titleBg.fillRoundedRect(width / 2 - 160, height / 2 - 60, 320, 80, 12);

    // Title text
    const title = this.add.text(width / 2, height / 2 - 20, 'NEON RUNNER', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '36px',
      fontStyle: 'bold',
      color: '#00ffcc',
      stroke: '#9900ff',
      strokeThickness: 4,
      shadow: {
        offsetX: 0,
        offsetY: 0,
        color: '#00ffcc',
        blur: 20,
        fill: true,
      }
    }).setOrigin(0.5);

    const subtitle = this.add.text(width / 2, height / 2 + 28, 'Loading...', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '16px',
      color: '#cc88ff',
    }).setOrigin(0.5);

    // Animated loading dots
    let dotCount = 0;
    const dotTimer = this.time.addEvent({
      delay: 300,
      loop: true,
      callback: () => {
        dotCount = (dotCount + 1) % 4;
        subtitle.setText('Loading' + '.'.repeat(dotCount));
      }
    });

    // Pulsing title
    this.tweens.add({
      targets: title,
      scaleX: 1.05,
      scaleY: 1.05,
      duration: 800,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });

    // Move to MenuScene after short delay
    this.time.delayedCall(1800, () => {
      dotTimer.remove();
      this.cameras.main.fadeOut(400, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('MenuScene');
      });
    });
  }
}
