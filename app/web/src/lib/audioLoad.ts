/** True when this fetch generation is still the latest (apply the blob URL). */
export function shouldApplyAudioResult(resultGen: number, currentGen: number): boolean {
  return resultGen === currentGen;
}
