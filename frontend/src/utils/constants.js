/**
 * Workout Form Coach Constants
 */

export const EXERCISES = [
  {
    id: 'squat',
    name: 'Squat',
    shortName: 'Squat',
    targetMuscles: 'Quadriceps, Glutes, Hamstrings, Core',
    standardRom: '110°–115° Knee Flexion (Parallel or below)',
    standardTempo: '3-1-1 / 2.4s Cycle',
    icon: 'sports_gymnastics',
    description: 'Lower-body compound movement tracking hip depth, knee track alignment, and spine neutrality.',
  },
  {
    id: 'pushup',
    name: 'Push-up',
    shortName: 'Push-up',
    targetMuscles: 'Pectoralis Major, Triceps, Anterior Deltoid, Core',
    standardRom: '90° Elbow Flexion (Chest 2" off floor)',
    standardTempo: '2-1-1 / 2.0s Cycle',
    icon: 'fitness_center',
    description: 'Upper-body pressing movement tracking elbow flare, full lockout, and core rigid alignment.',
  },
  {
    id: 'lunge',
    name: 'Lunge',
    shortName: 'Lunge',
    targetMuscles: 'Quadriceps, Gluteus Medius, Hamstrings',
    standardRom: '90° Front & Back Knee Angles',
    standardTempo: '2-1-1 / 2.2s Cycle',
    icon: 'directions_walk',
    description: 'Unilateral movement tracking knee valgus, pelvic alignment, and stride balance.',
  },
];

export const JOB_STATUSES = {
  QUEUED: 'queued',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
};

export const PIPELINE_STEPS = [
  { id: 1, label: 'Uploading workout clip', duration: 'Done' },
  { id: 2, label: 'Reading video frames', duration: 'Done' },
  { id: 3, label: 'Tracking body movement', duration: 'Active' },
  { id: 4, label: 'Counting reps & timing tempo', duration: 'Pending' },
  { id: 5, label: 'Checking movement depth & form', duration: 'Pending' },
  { id: 6, label: 'Preparing coaching feedback', duration: 'Pending' },
];

export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB
export const MAX_VIDEO_DURATION_SECONDS = 60; // 60 seconds
export const ALLOWED_MIME_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'video/x-m4v',
];
