/**
 * Config-Driven Rep State Machine & Joint Angle Rules
 *
 * Implements deterministic up -> down -> up rep segmentation using joint angle fixtures.
 * Requires zero neural models, allowing standalone unit testing on CI/CD pipelines.
 */

/**
 * Calculate 2D/3D angle in degrees between three keypoints (A - B - C)
 * where B is the vertex joint (e.g. hip-knee-ankle for knee angle).
 * @param {{x: number, y: number}} a
 * @param {{x: number, y: number}} b Vertex
 * @param {{x: number, y: number}} c
 * @returns {number} Angle in degrees (0 - 180)
 */
export function calculateJointAngle(a, b, c) {
  if (!a || !b || !c) return 0;
  const radians = Math.atan2(c.y - b.y, c.x - b.x) - Math.atan2(a.y - b.y, a.x - b.x);
  let angle = Math.abs((radians * 180.0) / Math.PI);
  if (angle > 180.0) {
    angle = 360.0 - angle;
  }
  return Math.round(angle * 10) / 10;
}

/**
 * Exercise rule configurations
 * Adding a new exercise requires adding an entry to this configuration object, not modifying the engine code.
 */
export const EXERCISE_CONFIGS = {
  squat: {
    name: 'Squat',
    vertexJoint: 'knee',
    keypoints: ['hip', 'knee', 'ankle'],
    startThreshold: 160, // Standing extension
    inflectionThreshold: 110, // Full depth inflection
    standardRom: 110,
    minDurationSeconds: 1.2,
    rules: [
      {
        id: 'insufficient_depth',
        title: 'Shallow Depth',
        evaluate: (minAngle) => minAngle > 112,
        severity: 'notice',
        description: 'Squat depth stopped before reaching parallel plane (110° standard).',
      },
      {
        id: 'knee_cave',
        title: 'Knee Cave (Valgus)',
        evaluate: (_, keypoints) => keypoints?.kneeValgusAngle && keypoints.kneeValgusAngle < -3.5,
        severity: 'warning',
        description: 'Inward knee tracking observed during turnaround phase.',
      },
    ],
  },
  pushup: {
    name: 'Push-up',
    vertexJoint: 'elbow',
    keypoints: ['shoulder', 'elbow', 'wrist'],
    startThreshold: 160, // Arms extended lockout
    inflectionThreshold: 90, // Chest to floor
    standardRom: 90,
    minDurationSeconds: 1.0,
    rules: [
      {
        id: 'incomplete_lockout',
        title: 'Incomplete Lockout',
        evaluate: (minAngle, _, maxAngle) => maxAngle < 155,
        severity: 'notice',
        description: 'Elbows did not achieve full extension at top of rep.',
      },
    ],
  },
  lunge: {
    name: 'Lunge',
    vertexJoint: 'front_knee',
    keypoints: ['hip', 'front_knee', 'ankle'],
    startThreshold: 160,
    inflectionThreshold: 95,
    standardRom: 90,
    minDurationSeconds: 1.0,
    rules: [],
  },
};

/**
 * Deterministic Rep State Machine
 */
export class RepStateMachine {
  constructor(exerciseType = 'squat') {
    this.config = EXERCISE_CONFIGS[exerciseType] || EXERCISE_CONFIGS.squat;
    this.state = 'UP'; // 'UP' | 'DESCENDING' | 'BOTTOM' | 'ASCENDING'
    this.reps = [];
    this.currentRep = null;
    this.repCounter = 0;
  }

  /**
   * Process a frame's angle and timestamp
   * @param {number} angle Measured joint angle
   * @param {number} timestamp Timestamp in seconds
   * @param {any} [extraData] Additional landmarks data
   */
  processFrame(angle, timestamp, extraData = {}) {
    const { startThreshold, inflectionThreshold, minDurationSeconds, rules } = this.config;

    switch (this.state) {
      case 'UP':
        if (angle < startThreshold - 10) {
          this.state = 'DESCENDING';
          this.currentRep = {
            rep_number: this.repCounter + 1,
            start_time: timestamp,
            min_angle: angle,
            max_angle: angle,
            issues: [],
          };
        }
        break;

      case 'DESCENDING':
        if (this.currentRep) {
          this.currentRep.min_angle = Math.min(this.currentRep.min_angle, angle);
          this.currentRep.max_angle = Math.max(this.currentRep.max_angle, angle);
        }
        if (angle <= inflectionThreshold) {
          this.state = 'BOTTOM';
        } else if (angle >= startThreshold - 5) {
          // False start / abort
          this.state = 'UP';
          this.currentRep = null;
        }
        break;

      case 'BOTTOM':
        if (this.currentRep) {
          this.currentRep.min_angle = Math.min(this.currentRep.min_angle, angle);
        }
        if (angle > inflectionThreshold + 10) {
          this.state = 'ASCENDING';
        }
        break;

      case 'ASCENDING':
        if (this.currentRep) {
          this.currentRep.max_angle = Math.max(this.currentRep.max_angle, angle);
        }
        if (angle >= startThreshold - 5) {
          const duration = timestamp - (this.currentRep?.start_time || 0);
          if (duration >= minDurationSeconds) {
            this.repCounter += 1;
            const completedRep = {
              ...this.currentRep,
              rep_number: this.repCounter,
              end_time: timestamp,
              rom: Math.round(180 - (this.currentRep?.min_angle || 110)),
              tempo: Math.round(duration * 10) / 10,
              score: Math.max(70, Math.min(100, Math.round(100 - Math.max(0, (this.currentRep?.min_angle || 110) - inflectionThreshold) * 1.5))),
              is_flagged: false,
            };

            // Evaluate rule-based form flags
            for (const rule of rules) {
              if (rule.evaluate(completedRep.min_angle, extraData, completedRep.max_angle)) {
                completedRep.is_flagged = true;
                completedRep.fault_label = rule.title;
                completedRep.issues.push({
                  severity: rule.severity,
                  title: rule.title,
                  description: rule.description,
                });
              }
            }

            completedRep.status_label = completedRep.is_flagged ? 'FLAGGED' : 'CLEAN';
            this.reps.push(completedRep);
          }
          this.state = 'UP';
          this.currentRep = null;
        }
        break;
    }

    return {
      state: this.state,
      repCount: this.repCounter,
      reps: [...this.reps],
    };
  }
}
