import { expect, test } from 'claude-code/testing'
import { isNewer } from './register'

test('isNewer compares x.y.z numerically', async () => {
  expect(isNewer('0.4.7', '0.4.6')).toBe(true)
  expect(isNewer('0.10.0', '0.9.9')).toBe(true)
  expect(isNewer('1.0', '0.9.9')).toBe(true)
  expect(isNewer('0.4.6', '0.4.6')).toBe(false)
  expect(isNewer('0.4.5', '0.4.6')).toBe(false)
  expect(isNewer('', '0.4.6')).toBe(false)
})
