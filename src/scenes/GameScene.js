import Phaser from 'phaser';

const GROUND_Y = 587;   // y position of top of ground
const PLAYER_X = 80;

export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });
  }

  init() {
    this.score = 0;
    this.lives = 3;
    this.isGameOver = false;
    this.isInvincible = false;
    this.jumpCount = 0;
    this.maxJumps = 2;
    this.gameSpeed = 280;
    this.speedIncrement = 20;
    this.speedTimer = 0;
    this.combo = 0;
    this.comboTimer = 0;
    this.obstacleInterval = 1800;
    this.coinInterval = 2200;
    this.distanceSinceLastObstacle = 0;
  }

  create() {
    const { width, height } = this.scale;

    // Audio context
    this.audioCtx = null;
    try {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {}

    // Background
    this.bg = this.add.tileSprite(width / 2, height / 2, width, height, 'background');

    // Clouds
    this.cloudsGroup = this.add.group();
    for (let i = 0; i < 5; i++) {
      const key = i % 2 === 0 ? 'cloud1' : 'cloud2';
      const c = this.add.image(
        Phaser.Math.Between(0, width),
        Phaser.Math.Between(60, 240),
        key
      ).setAlpha(0.65);
      this.cloudsGroup.add(c);
    }

    // Ground tiles (2 for seamless scrolling)
    this.ground1 = this.add.tileSprite(width / 2, height - 40, width, 80, 'ground');
    this.ground2 = this.add.tileSprite(width / 2, height - 40, width, 80, 'ground');
    this.ground2.x = width * 1.5;

    // Physics groups
    this.obstacles = this.physics.add.group();
    this.coins = this.physics.add.group();

    // Player
    this.player = this.physics.add.sprite(PLAYER_X, GROUND_Y - 50, 'player_run1');
    this.player.setCollideWorldBounds(false);
    this.player.body.setSize(30, 44);
    this.player.body.setOffset(9, 4);

    // Ground collider (invisible static body)
    this.groundBody = this.physics.add.staticGroup();
    const groundBlock = this.groundBody.create(width / 2, GROUND_Y + 20, null);
    groundBlock.setVisible(false);
    groundBlock.body.setSize(width * 3, 40);

    this.physics.add.collider(this.player, this.groundBody, () => {
      this.jumpCount = 0;
    });

    // Particle emitters
    this.sparkEmitter = this.add.particles(0, 0, 'spark', {
      speed: { min: 80, max: 200 },
      angle: { min: -150, max: -30 },
      scale: { start: 1.2, end: 0 },
      lifespan: 500,
      quantity: 0,
      gravityY: 400,
      tint: [0xffff00, 0xff8800, 0xff00ff],
    });

    this.neonEmitter = this.add.particles(0, 0, 'neon_dot', {
      speed: { min: 60, max: 160 },
      angle: { min: 0, max: 360 },
      scale: { start: 1, end: 0 },
      lifespan: 400,
      quantity: 0,
      tint: [0x00ffcc, 0xcc00ff],
    });

    // Animations
    this.anims.create({
      key: 'run',
      frames: [
        { key: 'player_run1' },
        { key: 'player_run2' },
        { key: 'player_run3' },
        { key: 'player_run4' },
      ],
      frameRate: 10,
      repeat: -1,
    });
    this.anims.create({ key: 'jump', frames: [{ key: 'player_jump' }], frameRate: 1 });
    this.anims.create({ key: 'hurt', frames: [{ key: 'player_hurt' }], frameRate: 1 });

    this.anims.create({
      key: 'bird_fly',
      frames: [{ key: 'bird1' }, { key: 'bird2' }],
      frameRate: 8,
      repeat: -1,
    });

    this.player.play('run');

    // UI
    this.createUI();

    // Obstacle & coin timers
    this.obstacleTimer = this.time.addEvent({
      delay: this.obstacleInterval,
      loop: true,
      callback: this.spawnObstacle,
      callbackScope: this,
    });

    this.coinTimer = this.time.addEvent({
      delay: this.coinInterval,
      loop: true,
      callback: this.spawnCoin,
      callbackScope: this,
    });

    // Speed increase timer
    this.time.addEvent({
      delay: 8000,
      loop: true,
      callback: () => {
        this.gameSpeed = Math.min(this.gameSpeed + this.speedIncrement, 700);
        this.obstacleInterval = Math.max(this.obstacleInterval - 80, 900);
        this.obstacleTimer.reset({
          delay: this.obstacleInterval,
          loop: true,
          callback: this.spawnObstacle,
          callbackScope: this,
        });
        this.playSound('speedup');
        this.showFloatingText(this.scale.width / 2, 160, 'SPEED UP!', '#ff6600');
      }
    });

    // Input
    this.jumpKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);
    this.input.on('pointerdown', this.handleJump, this);
    this.jumpKey.on('down', this.handleJump, this);

    // Mobile jump button
    const btnSize = 90;
    this.jumpBtn = this.add.image(
      this.scale.width - btnSize / 2 - 16,
      this.scale.height - btnSize / 2 - 16,
      'jump_button'
    ).setDisplaySize(btnSize, btnSize).setAlpha(0.8).setInteractive();
    this.jumpBtn.on('pointerdown', this.handleJump, this);

    // Overlaps
    this.physics.add.overlap(this.player, this.obstacles, this.hitObstacle, null, this);
    this.physics.add.overlap(this.player, this.coins, this.collectCoin, null, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
  }

  createUI() {
    const { width } = this.scale;

    // Score
    this.scoreText = this.add.text(width / 2, 18, '0', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '32px',
      fontStyle: 'bold',
      color: '#00ffcc',
      stroke: '#000000',
      strokeThickness: 3,
    }).setOrigin(0.5, 0);

    // Distance label
    this.add.text(width / 2, 52, 'SCORE', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '10px',
      color: '#886699',
    }).setOrigin(0.5, 0);

    // Hearts
    this.hearts = [];
    for (let i = 0; i < 3; i++) {
      const h = this.add.image(18 + i * 28, 20, 'heart_full').setOrigin(0, 0);
      this.hearts.push(h);
    }

    // Combo text
    this.comboText = this.add.text(width - 12, 18, '', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '16px',
      color: '#ffcc00',
      stroke: '#000000',
      strokeThickness: 2,
    }).setOrigin(1, 0).setAlpha(0);

    // Speed indicator
    this.speedText = this.add.text(12, 52, 'SPD: 1x', {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '10px',
      color: '#775599',
    }).setOrigin(0, 0);
  }

  handleJump() {
    if (this.isGameOver) return;
    if (this.jumpCount < this.maxJumps) {
      this.player.setVelocityY(-700);
      this.jumpCount++;
      this.player.play('jump');
      this.playSound('jump');

      // Double jump particle burst
      if (this.jumpCount === 2) {
        this.neonEmitter.emitParticleAt(this.player.x, this.player.y + 20, 12);
        this.playSound('doublejump');
      }
    }
  }

  spawnObstacle() {
    if (this.isGameOver) return;
    const { width } = this.scale;
    const type = Phaser.Math.Between(0, 2);

    if (type === 0) {
      // Ground rock
      const rock = this.obstacles.create(width + 30, GROUND_Y - 26, 'rock');
      rock.body.allowGravity = false;
      rock.body.setSize(34, 44);
      rock.body.setOffset(7, 8);
      rock.obstacleType = 'rock';
    } else if (type === 1) {
      // Low bird (duck to avoid)
      const bird = this.obstacles.create(width + 30, GROUND_Y - 90, 'bird1');
      bird.play('bird_fly');
      bird.body.allowGravity = false;
      bird.body.setSize(36, 20);
      bird.body.setOffset(8, 6);
      bird.obstacleType = 'bird';
    } else {
      // High bird (jump to avoid or duck)
      const bird = this.obstacles.create(width + 30, GROUND_Y - 160, 'bird1');
      bird.play('bird_fly');
      bird.body.allowGravity = false;
      bird.body.setSize(36, 20);
      bird.body.setOffset(8, 6);
      bird.obstacleType = 'bird_high';
    }
  }

  spawnCoin() {
    if (this.isGameOver) return;
    const { width } = this.scale;
    const yPos = Phaser.Math.Between(GROUND_Y - 160, GROUND_Y - 60);
    const coin = this.coins.create(width + 20, yPos, 'coin');
    coin.body.allowGravity = false;

    // Bobbing animation
    this.tweens.add({
      targets: coin,
      y: yPos - 12,
      duration: 500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  hitObstacle(player, obstacle) {
    if (this.isInvincible || this.isGameOver) return;

    // Remove obstacle
    this.sparkEmitter.emitParticleAt(obstacle.x, obstacle.y, 20);
    obstacle.destroy();

    this.lives--;
    this.updateHearts();
    this.combo = 0;
    this.comboText.setAlpha(0);
    this.playSound('hit');

    if (this.lives <= 0) {
      this.triggerGameOver();
      return;
    }

    // Invincibility period
    this.isInvincible = true;
    this.player.play('hurt');
    this.cameras.main.shake(300, 0.015);

    // Flash player
    let flashCount = 0;
    const flashTimer = this.time.addEvent({
      delay: 100,
      repeat: 10,
      callback: () => {
        this.player.setAlpha(this.player.alpha < 1 ? 1 : 0.3);
        flashCount++;
        if (flashCount >= 10) {
          this.player.setAlpha(1);
          this.isInvincible = false;
          if (!this.player.body.blocked.down) {
            this.player.play('jump');
          } else {
            this.player.play('run');
          }
        }
      }
    });
  }

  collectCoin(player, coin) {
    this.neonEmitter.emitParticleAt(coin.x, coin.y, 8);
    coin.destroy();
    this.score += 10 * (1 + Math.floor(this.combo / 5));
    this.combo++;
    this.comboTimer = 3000;
    this.playSound('coin');

    if (this.combo >= 3) {
      this.updateComboDisplay();
    }
    this.showFloatingText(coin.x, coin.y, '+10', '#ffdd00');
  }

  updateComboDisplay() {
    if (this.combo >= 3) {
      this.comboText.setText(`x${this.combo} COMBO`);
      this.comboText.setAlpha(1);
      this.tweens.add({
        targets: this.comboText,
        scaleX: 1.2,
        scaleY: 1.2,
        duration: 100,
        yoyo: true,
      });
    }
  }

  updateHearts() {
    this.hearts.forEach((h, i) => {
      h.setTexture(i < this.lives ? 'heart_full' : 'heart_empty');
    });
  }

  triggerGameOver() {
    this.isGameOver = true;
    this.player.play('hurt');
    this.player.setVelocityY(-400);
    this.sparkEmitter.emitParticleAt(this.player.x, this.player.y, 30);
    this.cameras.main.shake(500, 0.025);
    this.playSound('gameover');

    // Save high score
    const best = parseInt(localStorage.getItem('neonRunnerBest') || '0');
    if (this.score > best) {
      localStorage.setItem('neonRunnerBest', this.score.toString());
    }

    this.time.delayedCall(1200, () => {
      this.cameras.main.fadeOut(400, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.obstacleTimer.remove();
        this.coinTimer.remove();
        this.scene.start('GameOverScene', { score: this.score });
      });
    });
  }

  showFloatingText(x, y, message, color = '#ffffff') {
    const txt = this.add.text(x, y, message, {
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '18px',
      fontStyle: 'bold',
      color,
      stroke: '#000000',
      strokeThickness: 2,
    }).setOrigin(0.5);

    this.tweens.add({
      targets: txt,
      y: y - 60,
      alpha: 0,
      duration: 900,
      ease: 'Power2',
      onComplete: () => txt.destroy(),
    });
  }

  playSound(type) {
    if (!this.audioCtx) return;
    try {
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();
      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      switch (type) {
        case 'jump':
          osc.frequency.setValueAtTime(300, this.audioCtx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(600, this.audioCtx.currentTime + 0.1);
          gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.2);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.2);
          break;
        case 'doublejump':
          osc.frequency.setValueAtTime(500, this.audioCtx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(900, this.audioCtx.currentTime + 0.15);
          gain.gain.setValueAtTime(0.18, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.25);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.25);
          break;
        case 'coin':
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(880, this.audioCtx.currentTime);
          osc.frequency.setValueAtTime(1200, this.audioCtx.currentTime + 0.05);
          gain.gain.setValueAtTime(0.12, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.2);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.2);
          break;
        case 'hit':
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(200, this.audioCtx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(80, this.audioCtx.currentTime + 0.3);
          gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.3);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.3);
          break;
        case 'gameover':
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(400, this.audioCtx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(60, this.audioCtx.currentTime + 0.8);
          gain.gain.setValueAtTime(0.25, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.8);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.8);
          break;
        case 'speedup':
          osc.type = 'square';
          osc.frequency.setValueAtTime(400, this.audioCtx.currentTime);
          osc.frequency.linearRampToValueAtTime(800, this.audioCtx.currentTime + 0.15);
          gain.gain.setValueAtTime(0.1, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.2);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.2);
          break;
      }
    } catch (e) {}
  }

  update(time, delta) {
    if (this.isGameOver) return;

    const dt = delta / 1000;

    // Scroll ground
    this.ground1.tilePositionX += this.gameSpeed * dt;
    this.ground2.tilePositionX += this.gameSpeed * dt;

    // Scroll clouds (slower parallax)
    this.cloudsGroup.getChildren().forEach(c => {
      c.x -= 0.4;
      if (c.x < -100) c.x = this.scale.width + 100;
    });

    // Score
    this.score += Math.round(this.gameSpeed * dt * 0.1);
    this.scoreText.setText(this.score.toString());

    // Speed display
    const speedLevel = ((this.gameSpeed - 280) / 20 + 1).toFixed(1);
    this.speedText.setText(`SPD: ${speedLevel}x`);

    // Move obstacles
    this.obstacles.getChildren().forEach(obs => {
      obs.x -= this.gameSpeed * dt;
      if (obs.x < -80) obs.destroy();
    });

    // Move coins
    this.coins.getChildren().forEach(coin => {
      coin.x -= (this.gameSpeed * 0.9) * dt;
      if (coin.x < -30) coin.destroy();
    });

    // Player animation state
    if (!this.isInvincible) {
      if (this.player.body.blocked.down) {
        if (this.player.anims.currentAnim?.key !== 'run') {
          this.player.play('run');
        }
      } else {
        if (this.player.anims.currentAnim?.key !== 'jump') {
          this.player.play('jump');
        }
      }
    }

    // Combo decay
    if (this.combo > 0) {
      this.comboTimer -= delta;
      if (this.comboTimer <= 0) {
        this.combo = 0;
        this.tweens.add({
          targets: this.comboText,
          alpha: 0,
          duration: 300,
        });
      }
    }

    // Near-miss bonus (when obstacle passes player closely without collision)
    this.obstacles.getChildren().forEach(obs => {
      if (!obs.nearMissChecked && obs.x < PLAYER_X - 10 && obs.x > PLAYER_X - 50) {
        obs.nearMissChecked = true;
        this.score += 5;
        this.showFloatingText(PLAYER_X + 30, GROUND_Y - 80, 'CLOSE!', '#ff8800');
      }
    });
  }
}
