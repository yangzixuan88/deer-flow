import { checkpointManager } from '../domain/m11/adapters/executor_adapter.ts';
console.log('prototype methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(checkpointManager)).filter(n => n.includes('Interrupt') || n === 'recordRealInterruption' || n === 'getInterruptionInfo'));
console.log('has getInterruptionInfo:', typeof checkpointManager.getInterruptionInfo);
console.log('has recordRealInterruption:', typeof checkpointManager.recordRealInterruption);
