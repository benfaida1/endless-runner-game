import Phaser from 'phaser';

// ─── Constants ────────────────────────────────────────────────────────────────
const GAME_WIDTH = 375;
const GAME_HEIGHT = 667;
const GROUND_HEIGHT = 80;
const GROUND_TOP = GAME_HEIGHT - GROUND_HEIGHT;   // y = 587  (top of ground strip)
const PLAYER_X = 80;
const BASE_SPEED = 280;
const SPEED_INCREMENT = 30;
const MAX_SPEED = 720;
const JUMP_VELOCITY = -720;
const DOUBLE_JUMP_VELOCITY = -620;

// Bird heights above ground top
const BIRD_TIERS = [95, 160, 230];

export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });
  }

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  init() {
    this.gameSpeed   = BASE_SPEED;
    this.score       = 0;
    this.lives       = 3;
    this.isAlive     = true;
    this.isInvincible = false;
    this.jumpCount   = 0;       // 0 = on ground, 1 = first jump, 2 = used double jump
    this.elapsed     = 0;       // seconds
    this.lastSpeedUp = 0;       // seconds
    this.combo       = 0;
    this.multiplier  = 1;
    this.comboDecay  = 0;       // ms until combo resets
  }

  create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // ── Audio ──
    this._initAudio();

    // ── Background ──
    this.bgImage = this.add.image(W / 2, H / 2, 'background').setDisplaySize(W, H).setDepth(0);

    // ── Clouds ──
    this._cloudData = [];
    ['cloud1', 'cloud2', 'cloud1', 'cloud2', 'cloud1'].forEach((key, i) => {
      const spr = this.add.image(
        Phaser.Math.Between(20, W),
        Phaser.Math.Between(50, 280),
        key
      ).setAlpha(Phaser.Math.FloatBetween(0.35, 0.65)).setDepth(1);
      this._cloudData.push({ spr, speed: Phaser.Math.FloatBetween(0.12, 0.35) });
    });

    // ── Ground ──
    this.groundTile = this.add.tileSprite(W / 2, GROUND_TOP + GROUND_HEIGHT / 2, W, GROUND_HEIGHT, 'ground').setDepth(3);

    // ── Physics ──
    this.obstacles = this.physics.add.group();

    // ── Ground collider (static) ──
    this.groundStatic = this.physics.add.staticGroup();
    const gBlock = this.groundStatic.create(W / 2, GROUND_TOP + 8, null);
    gBlock.setVisible(false);
    gBlock.body.setSize(W * 4, 20);
    gBlock.refreshBody();

    // ── Player ──
    this._createPlayer();

    // ── Colliders / Overlaps ──
    this.physics.add.collider(this.player, this.groundStatic, () => {
      if (this.jumpCount !== 0) {
        this.jumpCount = 0;
        if (!this.isInvincible) this.player.play('run');
        this._spawnLandDust();
      }
    });

    this.physics.add.overlap(this.player, this.obstacles, this._onHit, null, this);

    // ── Particles (emitters) ──
    this._setupParticles();

    // ── UI ──
    this._createUI();

    // ── Input ──
    this._setupInput();

    // ── Timers ──
    this._obstacleTimer = this.time.addEvent({
      delay: this._nextObstacleDelay(),
      callback: this._spawnObstacle,
      callbackScope: this,
    });

    this._scoreTimer = this.time.addEvent({
      delay: 100,
      loop: true,
      callback: this._tickScore,
      callbackScope: this,
    });

    // ── Fade In ──
    this.cameras.main.fadeIn(300, 0, 0, 0);
  }

  // ─── Audio ────────────────────────────────────────────────────────────────

  _initAudio() {
    try {
      this._ac = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      this._ac = null;
    }
  }

  _tone(freq, dur, type = 'square', vol = 0.14, freqEnd = null) {
    if (!this._ac) return;
    try {
      const osc = this._ac.createOscillator();
      const gain = this._ac.createGain();
      osc.connect(gain);
      gain.connect(this._ac.destination);
      osc.type = type;
      const t = this._ac.currentTime;
      osc.frequency.setValueAtTime(freq, t);
      if (freqEnd) osc.frequency.exponentialRampToValueAtTime(freqEnd, t + dur);
      gain.gain.setValueAtTime(vol, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
      osc.start(t);
      osc.stop(t + dur + 0.01);
    } catch (e) { /* silent */ }
  }

  _sfxJump()       { this._tone(300, 0.09, 'square', 0.13, 560); }
  _sfxDoubleJump() {
    this._tone(420, 0.08, 'sine', 0.13, 700);
    this.time.delayedCall(70, () => this._tone(800, 0.1, 'sine', 0.1));
  }
  _sfxHit() {
    this._tone(220, 0.05, 'sawtooth', 0.22, 80);
    this.time.delayedCall(55, () => this._tone(130, 0.12, 'sawtooth', 0.18));
  }
  _sfxCoin()     { this._tone(1047, 0.06, 'triangle', 0.1, 1400); }
  _sfxCombo(n)   { const f = [523,659,784,1047,1319][Math.min(n-1,4)]; this._tone(f, 0.1, 'sine', 0.1); }
  _sfxSpeedUp()  {
    [400,600,800].forEach((f,i) => this.time.delayedCall(i*70, () => this._tone(f, 0.08, 'sine', 0.09)));
  }
  _sfxGameOver() {
    [380,300,220,160].forEach((f,i) => this.time.delayedCall(i*130, () => this._tone(f, 0.2, 'sawtooth', 0.2)));
  }

  // ─── Player ───────────────────────────────────────────────────────────────

  _createPlayer() {
    const W = this.scale.width;
    // Start just above ground
    this.player = this.physics.add.sprite(PLAYER_X, GROUND_TOP - 24, 'player_run1');
    this.player.setCollideWorldBounds(true);
    this.player.body.setSize(28, 44);
    this.player.body.setOffset(10, 4);

    // Define animations (guard against duplicate key errors on scene restart)
    const anim = (key, frames, rate, repeat) => {
      if (!this.anims.exists(key)) {
        this.anims.create({ key, frames: frames.map(k => ({ key: k })), frameRate: rate, repeat });
      }
    };
    anim('run',  ['player_run1','player_run2','player_run3','player_run4'], 10, -1);
    anim('jump', ['player_jump'], 1, 0);
    anim('hurt', ['player_hurt'], 1, 0);
    anim('bird_fly', ['bird1','bird2'], 7, -1);

    this.player.play('run');
  }

  // ─── Input ────────────────────────────────────────────────────────────────

  _setupInput() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Keyboard
    this.input.keyboard.on('keydown-SPACE', this._doJump, this);
    this.input.keyboard.on('keydown-UP',    this._doJump, this);
    this.input.keyboard.on('keydown-W',     this._doJump, this);

    // Tap anywhere except the jump button zone
    this.input.on('pointerdown', (ptr) => {
      const btnX = W - 60, btnY = H - 60;
      if (Math.hypot(ptr.x - btnX, ptr.y - btnY) > 58) {
        this._doJump();
      }
    });

    // On-screen jump button
    const btnSz = 90;
    const jumpBtn = this.add.image(W - 58, H - 58, 'jump_button')
      .setDisplaySize(btnSz, btnSz)
      .setAlpha(0.75)
      .setDepth(20)
      .setInteractive();

    jumpBtn.on('pointerdown', () => {
      this._doJump();
      this.tweens.add({ targets: jumpBtn, scaleX: 0.82, scaleY: 0.82, duration: 70, yoyo: true });
    });
  }

  _doJump() {
    if (!this.isAlive) return;

    // Resume AudioContext on first user gesture
    if (this._ac && this._ac.state === 'suspended') this._ac.resume();

    const onGround = this.player.body.blocked.down;

    if (onGround || this.jumpCount === 0) {
      this.player.setVelocityY(JUMP_VELOCITY);
      this.jumpCount = 1;
      this.player.play('jump');
      this._sfxJump();
      this._spawnJumpDust();
    } else if (this.jumpCount === 1) {
      this.player.setVelocityY(DOUBLE_JUMP_VELOCITY);
      this.jumpCount = 2;
      this.player.play('jump');
      this._sfxDoubleJump();
      this._spawnDoubleJumpFX();
    }
  }

  // ─── Obstacles ────────────────────────────────────────────────────────────

  _nextObstacleDelay() {
    // Gets shorter as score increases, floor at 850ms
    return Phaser.Math.Between(
      Math.max(850, 1700 - this.score * 0.4),
      Math.max(1100, 2200 - this.score * 0.5)
    );
  }

  _spawnObstacle() {
    if (!this.isAlive) return;
    const W = this.scale.width;
    const roll = Phaser.Math.Between(0, 3);
    if (roll === 0) {
      this._spawnBird(W + 30);
    } else {
      this._spawnRock(W + 30);
    }
    // Reschedule
    this._obstacleTimer = this.time.addEvent({
      delay: this._nextObstacleDelay(),
      callback: this._spawnObstacle,
      callbackScope: this,
    });
  }

  _spawnRock(x) {
    const rock = this.obstacles.create(x, GROUND_TOP - 22, 'rock');
    rock.body.allowGravity = false;
    rock.body.setImmovable(true);
    rock.body.setSize(34, 44);
    rock.body.setOffset(7, 6);
    rock.setData('type', 'rock');
    rock.setData('passed', false);
    const sc = Phaser.Math.FloatBetween(0.85, 1.25);
    rock.setScale(sc);
  }

  _spawnBird(x) {
    const tier = Phaser.Math.RND.pick(BIRD_TIERS);
    const y = GROUND_TOP - tier;
    const bird = this.obstacles.create(x, y, 'bird1');
    bird.body.allowGravity = false;
    bird.body.setImmovable(true);
    bird.body.setSize(36, 18);
    bird.body.setOffset(8, 7);
    bird.setData('type', 'bird');
    bird.setData('passed', false);
    bird.play('bird_fly');
  }

  // ─── Collision ────────────────────────────────────────────────────────────

  _onHit(player, obstacle) {
    if (this.isInvincible || !this.isAlive) return;
    const ox = obstacle.x, oy = obstacle.y;
    obstacle.destroy();
    this.lives--;
    this.combo = 0;
    this.multiplier = 1;
    this._updateComboUI();
    this._updateHeartsUI();
    this._sfxHit();
    this.cameras.main.shake(280, 0.013);
    this._spawnHitFX(ox, oy);
    this._spawnHitFX(player.x, player.y);

    if (this.lives <= 0) {
      this._gameOver();
    } else {
      this.isInvincible = true;
      this._flashPlayer(14, () => {
        this.isInvincible = false;
        if (this.player.active && this.isAlive) {
          this.player.setAlpha(1);
        }
      });
    }
  }

  _flashPlayer(times, onDone) {
    let count = 0;
    const ev = this.time.addEvent({
      delay: 100,
      repeat: times - 1,
      callback: () => {
        count++;
        if (this.player && this.player.active) {
          this.player.setAlpha(this.player.alpha < 0.5 ? 1 : 0.15);
        }
        if (count >= times) {
          if (this.player && this.player.active) this.player.setAlpha(1);
          if (onDone) onDone();
        }
      }
    });
  }

  // ─── Score & Speed ────────────────────────────────────────────────────────

  _tickScore() {
    if (!this.isAlive) return;
    this.score += this.multiplier;
    this._scoreText.setText(String(this.score).padStart(6, '0'));

    // Check near-miss for each obstacle
    this.obstacles.getChildren().forEach(obs => {
      if (!obs.getData('passed') && obs.x < PLAYER_X + 5 && obs.x > PLAYER_X - 60) {
        obs.setData('passed', true);
        this._onObstaclePassed(obs);
      }
    });
  }

  _onObstaclePassed(obs) {
    this.combo++;
    this.comboDecay = 4000;
    this.multiplier = Math.min(1 + Math.floor(this.combo / 2), 6);
    this._sfxCombo(this.combo);
    this._updateComboUI();
    this._showFloating(this.scale.width / 2 + Phaser.Math.Between(-40, 40), 160,
      this.combo >= 5 ? 'ON FIRE!' : this.combo >= 3 ? `COMBO x${this.combo}` : 'NICE!',
      ['#ffdd00','#ff8800','#ff4400','#ff00aa','#ff00ff'][Math.min(this.combo-1,4)]
    );
  }

  // ─── UI ───────────────────────────────────────────────────────────────────

  _createUI() {
    const W = this.scale.width;

    // Score backdrop
    const sbg = this.add.graphics().setDepth(10);
    sbg.fillStyle(0x000000, 0.55);
    sbg.fillRoundedRect(W / 2 - 80, 6, 160, 44, 8);

    this.add.text(W / 2, 12, 'SCORE', {
      fontFamily: '"Courier New", monospace',
      fontSize: '10px',
      color: '#8855aa',
    }).setOrigin(0.5, 0).setDepth(10);

    this._scoreText = this.add.text(W / 2, 20, '000000', {
      fontFamily: '"Courier New", monospace',
      fontSize: '22px',
      fontStyle: 'bold',
      color: '#00ffcc',
      stroke: '#003322',
      strokeThickness: 2,
    }).setOrigin(0.5, 0).setDepth(10);

    // Multiplier
    this._multText = this.add.text(W - 8, 8, 'x1', {
      fontFamily: '"Courier New", monospace',
      fontSize: '15px',
      fontStyle: 'bold',
      color: '#ffdd00',
    }).setOrigin(1, 0).setDepth(10);

    // Combo
    this._comboText = this.add.text(W - 8, 26, '', {
      fontFamily: '"Courier New", monospace',
      fontSize: '11px',
      color: '#ff8800',
    }).setOrigin(1, 0).setDepth(10);

    // Speed bar
    this._speedBg = this.add.graphics().setDepth(10);
    this._speedFill = this.add.graphics().setDepth(10);
    this._drawSpeedBar();

    // Hearts
    this._hearts = [];
    for (let i = 0; i < 3; i++) {
      const h = this.add.image(14 + i * 26, 14, 'heart_full')
        .setScale(0.85).setOrigin(0, 0).setDepth(10);
      this._hearts.push(h);
    }
  }

  _drawSpeedBar() {
    const W = this.scale.width;
    const bx = W / 2 - 50, by = 52, bw = 100, bh = 4;
    const pct = (this.gameSpeed - BASE_SPEED) / (MAX_SPEED - BASE_SPEED);
    this._speedBg.clear();
    this._speedBg.fillStyle(0x220033, 0.8);
    this._speedBg.fillRoundedRect(bx, by, bw, bh, 2);
    this._speedFill.clear();
    const c = Phaser.Display.Color.Interpolate.ColorWithColor(
      Phaser.Display.Color.ValueToColor(0x00ffcc),
      Phaser.Display.Color.ValueToColor(0xff0044),
      100, Math.min(100, Math.round(pct * 100))
    );
    this._speedFill.fillStyle(Phaser.Display.Color.GetColor(c.r, c.g, c.b), 1);
    this._speedFill.fillRoundedRect(bx, by, bw * pct, bh, 2);
  }

  _updateHeartsUI() {
    this._hearts.forEach((h, i) => h.setTexture(i < this.lives ? 'heart_full' : 'heart_empty'));
    this.tweens.add({
      targets: this._hearts,
      x: (t) => t.x + Phaser.Math.Between(-2, 2),
      duration: 50, yoyo: true, repeat: 3,
    });
  }

  _updateComboUI() {
    this._multText.setText('x' + this.multiplier);
    const cols = ['#ffdd00','#ff8800','#ff4400','#ff0088','#ff00ff','#cc00ff'];
    this._multText.setColor(cols[Math.min(this.multiplier - 1, cols.length - 1)]);
    this._comboText.setText(this.combo > 1 ? 'COMBO ' + this.combo : '');
  }

  _showFloating(x, y, msg, color) {
    const t = this.add.text(x, y, msg, {
      fontFamily: '"Courier New", monospace',
      fontSize: '20px',
      fontStyle: 'bold',
      color,
      stroke: '#000000',
      strokeThickness: 3,
    }).setOrigin(0.5).setDepth(20);
    this.tweens.add({
      targets: t,
      y: y - 55, alpha: 0, scaleX: 1.2, scaleY: 1.2,
      duration: 850, ease: 'Back.easeOut',
      onComplete: () => t.destroy(),
    });
  }

  // ─── Particles / FX ───────────────────────────────────────────────────────

  _setupParticles() {
    // Phaser 3.60+ uses new particle API; keep it simple with manual graphics
    // (Particle emitters are set up per-burst to avoid API version issues)
  }

  _spawnHitFX(x, y) {
    const cols = [0xff0044, 0xff6600, 0xffdd00, 0xff00ff, 0xffffff];
    for (let i = 0; i < 20; i++) {
      const g = this.add.graphics().setDepth(18);
      g.fillStyle(cols[i % cols.length], 1);
      const sz = Phaser.Math.Between(2, 6);
      g.fillRect(0, 0, sz, sz);
      g.x = x + Phaser.Math.Between(-8, 8);
      g.y = y + Phaser.Math.Between(-8, 8);
      const ang = Phaser.Math.Between(0, 360);
      const spd = Phaser.Math.Between(50, 200);
      this.tweens.add({
        targets: g,
        x: g.x + Math.cos(Phaser.Math.DegToRad(ang)) * spd * 0.5,
        y: g.y + Math.sin(Phaser.Math.DegToRad(ang)) * spd * 0.5,
        alpha: 0, scaleX: 0.1, scaleY: 0.1,
        duration: Phaser.Math.Between(350, 700),
        ease: 'Quad.easeOut',
        onComplete: () => g.destroy(),
      });
    }
    // Flash ring
    const ring = this.add.graphics().setDepth(19);
    ring.lineStyle(4, 0xffffff, 0.8);
    ring.strokeCircle(x, y, 12);
    this.tweens.add({
      targets: ring, scaleX: 3, scaleY: 3, alpha: 0, duration: 250,
      onComplete: () => ring.destroy(),
    });
  }

  _spawnJumpDust() {
    const px = this.player.x, py = this.player.y + 22;
    for (let i = 0; i < 7; i++) {
      const g = this.add.graphics().setDepth(5);
      g.fillStyle(0x9900ff, 0.85);
      const sz = Phaser.Math.Between(2, 5);
      g.fillRect(0, 0, sz, sz);
      g.x = px + Phaser.Math.Between(-14, 14);
      g.y = py;
      this.tweens.add({
        targets: g,
        x: g.x + Phaser.Math.Between(-22, 22),
        y: g.y + Phaser.Math.Between(8, 28),
        alpha: 0, duration: Phaser.Math.Between(200, 400),
        onComplete: () => g.destroy(),
      });
    }
  }

  _spawnDoubleJumpFX() {
    const px = this.player.x, py = this.player.y;
    // Expanding ring
    const ring = this.add.graphics().setDepth(9);
    ring.lineStyle(3, 0x00ffcc, 1);
    ring.strokeCircle(px, py, 8);
    this.tweens.add({
      targets: ring, scaleX: 5, scaleY: 5, alpha: 0, duration: 350,
      onComplete: () => ring.destroy(),
    });
    // Radial sparks
    for (let i = 0; i < 12; i++) {
      const g = this.add.graphics().setDepth(9);
      g.fillStyle(0x00ffff, 1);
      g.fillRect(0, 0, 3, 3);
      g.x = px; g.y = py;
      const a = (i / 12) * Math.PI * 2;
      this.tweens.add({
        targets: g,
        x: px + Math.cos(a) * 48,
        y: py + Math.sin(a) * 48,
        alpha: 0, duration: 280,
        onComplete: () => g.destroy(),
      });
    }
  }

  _spawnLandDust() {
    const px = this.player.x, py = this.player.y + 22;
    for (let i = 0; i < 9; i++) {
      const g = this.add.graphics().setDepth(5);
      g.fillStyle(0x6600cc, 0.9);
      const sz = Phaser.Math.Between(3, 7);
      g.fillRect(0, 0, sz, sz);
      g.x = px + Phaser.Math.Between(-18, 18);
      g.y = py;
      this.tweens.add({
        targets: g,
        x: g.x + Phaser.Math.Between(-30, 30),
        y: g.y + Phaser.Math.Between(6, 22),
        alpha: 0, duration: Phaser.Math.Between(240, 480),
        onComplete: () => g.destroy(),
      });
    }
  }

  _spawnRunTrail() {
    const g = this.add.graphics().setDepth(4);
    g.fillStyle(0x00ffcc, 0.35);
    g.fillRect(0, 0, 4, 4);
    g.x = this.player.x - 12;
    g.y = this.player.y + Phaser.Math.Between(-4, 4);
    this.tweens.add({
      targets: g, x: g.x - 18, alpha: 0, duration: 160,
      onComplete: () => g.destroy(),
    });
  }

  // ─── Game Over ────────────────────────────────────────────────────────────

  _gameOver() {
    this.isAlive = false;
    this._sfxGameOver();

    if (this._obstacleTimer) this._obstacleTimer.remove();
    if (this._scoreTimer)    this._scoreTimer.remove();

    // Save high score (use consistent key)
    const prev = parseInt(localStorage.getItem('neonRunnerHighScore') || '0', 10);
    const best = Math.max(prev, this.score);
    localStorage.setItem('neonRunnerHighScore', String(best));

    this.player.play('hurt');
    this.player.setVelocityY(JUMP_VELOCITY * 0.35);

    this.cameras.main.shake(450, 0.02);

    this._spawnHitFX(this.player.x, this.player.y);

    this.time.delayedCall(1400, () => {
      this.cameras.main.fadeOut(400, 0, 0, 0);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('GameOverScene', { score: this.score, highScore: best });
      });
    });
  }

  // ─── Update ───────────────────────────────────────────────────────────────

  update(time, delta) {
    if (!this.isAlive) {
      // Still scroll ground briefly after death for polish
      if (this.groundTile) this.groundTile.tilePositionX += this.gameSpeed * (delta / 1000) * 0.5;
      return;
    }

    const dt = delta / 1000;

    // ── Ground scroll ──
    this.groundTile.tilePositionX += this.gameSpeed * dt;

    // ── Obstacle movement ──
    this.obstacles.getChildren().forEach(obs => {
      obs.x -= this.gameSpeed * dt;
      if (obs.x < -120) obs.destroy();
    });

    // ── Cloud parallax ──
    this._cloudData.forEach(({ spr, speed }) => {
      spr.x -= speed * this.gameSpeed * dt * 0.2;
      if (spr.x < -120) {
        spr.x = this.scale.width + 100;
        spr.y = Phaser.Math.Between(50, 280);
      }
    });

    // ── Speed increase every 10 seconds ──
    this.elapsed += dt;
    if (this.elapsed - this.lastSpeedUp >= 10) {
      this.lastSpeedUp = this.elapsed;
      this.gameSpeed = Math.min(this.gameSpeed + SPEED_INCREMENT, MAX_SPEED);
      this._sfxSpeedUp();
      this._showFloating(this.scale.width / 2, 200, 'SPEED UP!', '#00ffff');
    }

    // ── Combo decay ──
    if (this.combo > 0) {
      this.comboDecay -= delta;
      if (this.comboDecay <= 0) {
        this.combo = 0;
        this.multiplier = 1;
        this._updateComboUI();
      }
    }

    // ── Speed bar ──
    this._drawSpeedBar();

    // ── Player tilt on air ──
    const onGround = this.player.body.blocked.down;
    if (!onGround) {
      const vy = this.player.body.velocity.y;
      this.player.setAngle(vy < 0 ? -10 : 7);
    } else {
      this.player.setAngle(0);
      // Ensure run anim when back on ground and not hurt-flashing
      if (!this.isInvincible && this.player.anims.currentAnim?.key !== 'run') {
        this.player.play('run');
      }
    }

    // ── Run trail ──
    if (Phaser.Math.Between(0, 4) === 0) {
      this._spawnRunTrail();
    }
  }
}
