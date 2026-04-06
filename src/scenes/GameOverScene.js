import Phaser from 'phaser';

export default class GameOverScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameOverScene' });
  }

  init(data) {
    this.finalScore = data.score || 0;
    this.bestScore = parseInt(localStorage.getItem('neonRunnerBest') || '0');
    this.isNewBest = this.finalScore >= this.bestScore && this.finalScore > 0;
  }

  create() {
    const { width, height } = this.scale;

    // Background
    this.add.image(width / 2, height / 2, 'background').setDisplaySize(width, height);

    // Falling sparks from top
    const sparks = this.add.particles(0, 0, 'spark', {
      x: { min: 0, max: width },
      y: -10,
      speedY: { min: 60, max: 140 },
      speedX: { min: -20, max: 20 },
      scale: { start: 1, end: 0 },
      lifespan: 2000,
      quantity: 2,
      frequency: 80,
      tint: [0xff00ff, 0x9900ff, 0x00ffcc],
    });

    // Panel background
    const panelGfx = this.add.graphics();
    panelGfx.fillStyle(0x11002b, 0.92);
    panelGfx.fillRoundedRect(width / 2 - 160, 130, 320, 380, 18);
    panelGfx.lineStyle(2, 0xcc00ff, 1);
    panelGfx.strokeRoundedRect(width / 2 - 160, 130, 320, 380, 18);

    // GAME OVER title
    const goText = this.add.text(width / 2, 170, 'GAME OVER', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '36px',
      fontStyle: 'bold',
      color: '#ff0055',
      stroke: '#440011',
      strokeThickness: 4,
    }).setOrigin(0.5).setAlpha(0);

    this.tweens.add({
      targets: goText,
      alpha: 1,
      duration: 500,
      delay: 200,
    });

    // Score display
    const scorePanel = this.add.graphics();
    scorePanel.fillStyle(0x220044, 0.8);
    scorePanel.fillRoundedRect(width / 2 - 120, 220, 240, 80, 10);

    this.add.text(width / 2, 240, 'SCORE', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '12px',
      color: '#886699',
      letterSpacing: 4,
    }).setOrigin(0.5);

    const scoreNum = this.add.text(width / 2, 272, '0', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '38px',
      fontStyle: 'bold',
      color: '#00ffcc',
    }).setOrigin(0.5);

    // Animate score counting up
    let displayScore = 0;
    const scoreStep = Math.max(1, Math.floor(this.finalScore / 40));
    const scoreCounter = this.time.addEvent({
      delay: 25,
      repeat: 40,
      callback: () => {
        displayScore = Math.min(displayScore + scoreStep, this.finalScore);
        scoreNum.setText(displayScore.toString());
      }
    });

    // Best score
    const bestY = 330;
    this.add.text(width / 2, bestY, 'BEST', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '11px',
      color: '#886699',
      letterSpacing: 4,
    }).setOrigin(0.5);

    this.add.text(width / 2, bestY + 26, this.bestScore.toString(), {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '28px',
      fontStyle: 'bold',
      color: '#ffcc00',
    }).setOrigin(0.5);

    // NEW BEST badge
    if (this.isNewBest) {
      const badge = this.add.text(width / 2 + 70, bestY - 10, 'NEW!', {
        fontFamily: '"Courier New", Courier, monospace',
        fontSize: '14px',
        fontStyle: 'bold',
        color: '#ff00ff',
        stroke: '#000000',
        strokeThickness: 2,
        backgroundColor: '#330044',
        padding: { x: 6, y: 3 },
      }).setOrigin(0.5).setAlpha(0);

      this.tweens.add({
        targets: badge,
        alpha: 1,
        scaleX: 1.2,
        scaleY: 1.2,
        duration: 300,
        delay: 1200,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.easeInOut',
      });

      // Confetti burst at new best
      this.time.delayedCall(1000, () => {
        for (let i = 0; i < 5; i++) {
          this.time.delayedCall(i * 100, () => {
            const x = Phaser.Math.Between(width / 2 - 100, width / 2 + 100);
            const confetti = this.add.particles(x, 350, 'star_particle', {
              speed: { min: 100, max: 250 },
              angle: { min: -120, max: -60 },
              scale: { start: 1, end: 0 },
              lifespan: 800,
              quantity: 8,
              tint: [0xff00ff, 0x00ffcc, 0xffcc00],
            });
            this.time.delayedCall(800, () => confetti.destroy());
          });
        }
      });
    }

    // Separator line
    const sepGfx = this.add.graphics();
    sepGfx.lineStyle(1, 0x440066, 0.8);
    sepGfx.lineBetween(width / 2 - 120, 390, width / 2 + 120, 390);

    // PLAY AGAIN button
    const btn1X = width / 2 - 110;
    const btn1Y = 408;
    const btn1W = 220;
    const btn1H = 55;

    const btn1Gfx = this.add.graphics();
    const drawBtn1 = (hover) => {
      btn1Gfx.clear();
      btn1Gfx.fillStyle(hover ? 0x44ffdd : 0x00ffcc, 1);
      btn1Gfx.fillRoundedRect(btn1X, btn1Y, btn1W, btn1H, 10);
      btn1Gfx.fillStyle(hover ? 0x22ddbb : 0x00ddaa, 0.5);
      btn1Gfx.fillRoundedRect(btn1X + 4, btn1Y + 4, btn1W - 8, btn1H / 2, 6);
    };
    drawBtn1(false);

    const playAgainTxt = this.add.text(width / 2, btn1Y + btn1H / 2, 'PLAY AGAIN', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '22px',
      fontStyle: 'bold',
      color: '#1a0533',
    }).setOrigin(0.5);

    const zone1 = this.add.zone(width / 2, btn1Y + btn1H / 2, btn1W, btn1H).setInteractive();
    zone1.on('pointerover', () => drawBtn1(true));
    zone1.on('pointerout', () => drawBtn1(false));
    zone1.on('pointerdown', () => {
      this.cameras.main.fadeOut(300, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('GameScene');
      });
    });

    // MENU button
    const btn2X = width / 2 - 110;
    const btn2Y = 476;
    const btn2W = 220;
    const btn2H = 45;

    const btn2Gfx = this.add.graphics();
    const drawBtn2 = (hover) => {
      btn2Gfx.clear();
      btn2Gfx.lineStyle(2, hover ? 0xcc44ff : 0x880088, 1);
      btn2Gfx.strokeRoundedRect(btn2X, btn2Y, btn2W, btn2H, 8);
      if (hover) {
        btn2Gfx.fillStyle(0x330055, 0.5);
        btn2Gfx.fillRoundedRect(btn2X, btn2Y, btn2W, btn2H, 8);
      }
    };
    drawBtn2(false);

    const menuTxt = this.add.text(width / 2, btn2Y + btn2H / 2, 'MAIN MENU', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '18px',
      color: '#cc88ff',
    }).setOrigin(0.5);

    const zone2 = this.add.zone(width / 2, btn2Y + btn2H / 2, btn2W, btn2H).setInteractive();
    zone2.on('pointerover', () => drawBtn2(true));
    zone2.on('pointerout', () => drawBtn2(false));
    zone2.on('pointerdown', () => {
      this.cameras.main.fadeOut(300, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('MenuScene');
      });
    });

    // Also allow tapping anywhere to restart (convenience)
    this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE).once('down', () => {
      this.cameras.main.fadeOut(300, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('GameScene');
      });
    });

    this.cameras.main.fadeIn(400, 0, 0, 0);
  }
}
