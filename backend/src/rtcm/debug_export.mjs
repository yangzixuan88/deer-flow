// Direct check - can tsx see the exported symbols?
import * as ea from '../domain/m11/adapters/executor_adapter.ts';
console.log('ea exports:', Object.keys(ea).filter(k => k.includes('Interrupt') || k === 'checkpointManager'));
