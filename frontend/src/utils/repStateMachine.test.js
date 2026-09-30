import { RepStateMachine, calculateJointAngle } from './repStateMachine.js';

// Unit Test Suite for State Machine & Geometry Engine
export function runUnitTests() {
  const results = [];

  // Test 1: Angle calculation
  const p1 = { x: 0, y: 1 };
  const vertex = { x: 0, y: 0 };
  const p2 = { x: 1, y: 0 };
  const angle = calculateJointAngle(p1, vertex, p2);
  results.push({
    test: 'Joint angle calculation (90 degree right angle)',
    passed: angle === 90,
    actual: angle,
  });

  // Test 2: Squat rep count from angle fixture
  const sm = new RepStateMachine('squat');
  // Standing at 0s
  sm.processFrame(170, 0.0);
  // Descending
  sm.processFrame(140, 0.5);
  sm.processFrame(120, 1.0);
  // Bottom inflection (105 deg parallel)
  sm.processFrame(105, 1.4);
  // Ascending
  sm.processFrame(130, 1.8);
  sm.processFrame(150, 2.2);
  // Lockout at top
  const res = sm.processFrame(165, 2.5);

  results.push({
    test: 'State machine segments clean squat rep (1 rep counted)',
    passed: res.repCount === 1 && res.reps.length === 1 && !res.reps[0].is_flagged,
    actual: `${res.repCount} reps, is_flagged: ${res.reps[0]?.is_flagged}`,
  });

  // Test 3: Shallow depth flagged rep
  const sm2 = new RepStateMachine('squat');
  sm2.processFrame(170, 0.0);
  sm2.processFrame(140, 0.5);
  // Bottom stopped at 118 deg (shallow)
  sm2.processFrame(118, 1.2);
  sm2.processFrame(145, 1.8);
  const res2 = sm2.processFrame(165, 2.4);

  results.push({
    test: 'Rule evaluation flags shallow depth rep (>112 deg)',
    passed: res2.repCount === 1 && res2.reps[0]?.is_flagged === true,
    actual: `fault_label: ${res2.reps[0]?.fault_label}`,
  });

  return results;
}
