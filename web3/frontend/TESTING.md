# 🧪 Testing Guide - Fibtool Frontend

Comprehensive testing strategy for the DApp.

---

## 🎯 Testing Philosophy

- **Test User Flows**: Focus on what users actually do
- **Mock Blockchain**: Use test data to avoid real transactions
- **Component Isolation**: Test components independently
- **Integration Testing**: Test full user journeys
- **Accessibility**: Ensure WCAG AA compliance

---

## 🛠️ Testing Tools

```bash
# Install testing dependencies
npm install --save-dev \
  @testing-library/react \
  @testing-library/jest-dom \
  @testing-library/user-event \
  jest \
  jest-environment-jsdom \
  @playwright/test
```

---

## 📦 Test Structure

```
__tests__/
├── unit/
│   ├── components/
│   │   ├── TokenBalance.test.tsx
│   │   ├── StrategyCard.test.tsx
│   │   └── StakingWidget.test.tsx
│   ├── hooks/
│   │   ├── useToken.test.ts
│   │   └── useStaking.test.ts
│   └── utils/
│       └── helpers.test.ts
├── integration/
│   ├── staking-flow.test.tsx
│   ├── marketplace-flow.test.tsx
│   └── governance-flow.test.tsx
└── e2e/
    ├── wallet-connection.spec.ts
    ├── strategy-purchase.spec.ts
    └── staking-journey.spec.ts
```

---

## 🧩 Unit Tests

### Testing Components

**Example: TokenBalance.test.tsx**

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { TokenBalance } from '@/components/TokenBalance';

// Mock wagmi
jest.mock('wagmi', () => ({
  useReadContract: jest.fn(() => ({
    data: BigInt('1000000000000000000'), // 1 FIBT
    isLoading: false,
    error: null,
  })),
}));

describe('TokenBalance', () => {
  it('renders balance correctly', async () => {
    render(<TokenBalance address="0x123..." />);
    
    await waitFor(() => {
      expect(screen.getByText('1.00 FIBT')).toBeInTheDocument();
    });
  });

  it('shows loading state', () => {
    // Mock loading state
    jest.mock('wagmi', () => ({
      useReadContract: jest.fn(() => ({
        data: null,
        isLoading: true,
        error: null,
      })),
    }));

    render(<TokenBalance address="0x123..." />);
    expect(screen.getByTestId('loading-shimmer')).toBeInTheDocument();
  });

  it('handles error state', () => {
    // Mock error
    jest.mock('wagmi', () => ({
      useReadContract: jest.fn(() => ({
        data: null,
        isLoading: false,
        error: new Error('Contract read failed'),
      })),
    }));

    render(<TokenBalance address="0x123..." />);
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
```

### Testing Hooks

**Example: useToken.test.ts**

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useTokenApproval } from '@/hooks/useToken';

describe('useToken hooks', () => {
  it('approves token spending', async () => {
    const { result } = renderHook(() => useTokenApproval());

    await waitFor(() => {
      expect(result.current.approve).toBeDefined();
    });

    // Simulate approval
    result.current.approve('0xSpender', BigInt('1000000000000000000'));

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
```

### Testing Utilities

**Example: helpers.test.ts**

```typescript
import {
  formatTokenAmount,
  parseTokenAmount,
  shortenAddress,
  calculateWinRate,
} from '@/utils/helpers';

describe('Helper Functions', () => {
  describe('formatTokenAmount', () => {
    it('formats 1 token correctly', () => {
      expect(formatTokenAmount(BigInt('1000000000000000000'))).toBe('1.00');
    });

    it('formats 1000 tokens with comma', () => {
      expect(formatTokenAmount(BigInt('1000000000000000000000'))).toBe('1,000.00');
    });

    it('handles zero', () => {
      expect(formatTokenAmount(BigInt('0'))).toBe('0.00');
    });
  });

  describe('shortenAddress', () => {
    it('shortens address correctly', () => {
      const address = '0x1234567890abcdef1234567890abcdef12345678';
      expect(shortenAddress(address)).toBe('0x1234...5678');
    });
  });

  describe('calculateWinRate', () => {
    it('calculates win rate', () => {
      expect(calculateWinRate(72, 100)).toBe(72);
    });

    it('handles no signals', () => {
      expect(calculateWinRate(0, 0)).toBe(0);
    });
  });
});
```

---

## 🔗 Integration Tests

### Staking Flow Test

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StakingPage from '@/app/staking/page';

describe('Staking Flow', () => {
  it('completes full staking journey', async () => {
    render(<StakingPage />);

    // 1. Select tier
    const goldTier = screen.getByText('Gold');
    fireEvent.click(goldTier);

    // 2. Enter amount
    const amountInput = screen.getByLabelText('Amount to Stake');
    fireEvent.change(amountInput, { target: { value: '5000' } });

    // 3. Enable auto-compound
    const autoCompound = screen.getByLabelText('Auto-compound');
    fireEvent.click(autoCompound);

    // 4. Click stake button
    const stakeButton = screen.getByText('Stake FIBT');
    fireEvent.click(stakeButton);

    // 5. Verify transaction initiated
    await waitFor(() => {
      expect(screen.getByText(/transaction pending/i)).toBeInTheDocument();
    });

    // 6. Mock transaction success
    await waitFor(() => {
      expect(screen.getByText(/staking successful/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });
});
```

### Marketplace Flow Test

```typescript
describe('Marketplace Flow', () => {
  it('searches and filters strategies', async () => {
    render(<MarketplacePage />);

    // 1. Search for strategy
    const searchInput = screen.getByPlaceholderText('Search strategies...');
    fireEvent.change(searchInput, { target: { value: 'Fibonacci' } });

    await waitFor(() => {
      expect(screen.getByText(/Fibonacci Retracement Master/i)).toBeInTheDocument();
    });

    // 2. Filter by category
    const categorySelect = screen.getByLabelText('Category');
    fireEvent.change(categorySelect, { target: { value: 'fibonacci' } });

    await waitFor(() => {
      const cards = screen.getAllByTestId('strategy-card');
      cards.forEach(card => {
        expect(card).toHaveTextContent(/fibonacci/i);
      });
    });

    // 3. Click strategy card
    const strategyCard = screen.getByText(/Fibonacci Retracement Master/i);
    fireEvent.click(strategyCard);

    // 4. Verify navigation to detail page
    await waitFor(() => {
      expect(window.location.pathname).toContain('/marketplace/');
    });
  });
});
```

---

## 🌐 E2E Tests (Playwright)

### Setup Playwright

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '__tests__/e2e',
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: true,
  },
});
```

### Wallet Connection Test

```typescript
import { test, expect } from '@playwright/test';

test('connects wallet and displays balance', async ({ page }) => {
  // Navigate to app
  await page.goto('/');

  // Click connect wallet
  await page.click('text=Connect Wallet');

  // Select MetaMask
  await page.click('text=MetaMask');

  // In real test, would interact with MetaMask popup
  // For testing, we can mock the wallet provider

  // Verify wallet connected
  await expect(page.locator('[data-testid="wallet-address"]')).toBeVisible();
  
  // Verify balance displayed
  await expect(page.locator('[data-testid="token-balance"]')).toContainText('FIBT');
});
```

### Strategy Purchase Journey

```typescript
test('purchases strategy signal', async ({ page, context }) => {
  // Connect wallet (reuse above)
  
  // Navigate to marketplace
  await page.goto('/marketplace');

  // Click strategy
  await page.click('text=Fibonacci Retracement Master');

  // Verify detail page
  await expect(page).toHaveURL(/\/marketplace\/\d+/);

  // Check balance before purchase
  const balanceBefore = await page.locator('[data-testid="balance"]').textContent();

  // Click subscribe
  await page.click('text=Subscribe');

  // Approve transaction in MetaMask (mocked)
  await page.click('text=Confirm');

  // Wait for transaction
  await page.waitForSelector('text=Purchase Successful', { timeout: 10000 });

  // Verify balance updated
  const balanceAfter = await page.locator('[data-testid="balance"]').textContent();
  expect(balanceAfter).not.toBe(balanceBefore);

  // Verify signal appears in profile
  await page.goto('/profile');
  await expect(page.locator('text=Fibonacci Retracement Master')).toBeVisible();
});
```

---

## 🎨 Visual Regression Testing

```typescript
import { test } from '@playwright/test';

test('homepage visual regression', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveScreenshot('homepage.png');
});

test('marketplace visual regression', async ({ page }) => {
  await page.goto('/marketplace');
  await expect(page).toHaveScreenshot('marketplace.png');
});
```

---

## ♿ Accessibility Testing

```typescript
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

describe('Accessibility', () => {
  it('has no violations on homepage', async () => {
    const { container } = render(<HomePage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('supports keyboard navigation', async () => {
    render(<Navbar />);
    
    // Tab through navigation
    userEvent.tab();
    expect(screen.getByText('Marketplace')).toHaveFocus();
    
    userEvent.tab();
    expect(screen.getByText('Staking')).toHaveFocus();
  });

  it('has proper ARIA labels', () => {
    render(<StakingWidget />);
    
    expect(screen.getByLabelText('Amount to Stake')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stake FIBT' })).toBeInTheDocument();
  });
});
```

---

## 📊 Performance Testing

```typescript
import { test, expect } from '@playwright/test';

test('performance metrics', async ({ page }) => {
  await page.goto('/');

  // Collect performance metrics
  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0];
    return {
      loadTime: navigation.loadEventEnd - navigation.loadEventStart,
      domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
      firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime,
    };
  });

  // Assert performance thresholds
  expect(metrics.loadTime).toBeLessThan(3000); // 3s
  expect(metrics.domContentLoaded).toBeLessThan(2000); // 2s
  expect(metrics.firstPaint).toBeLessThan(1500); // 1.5s
});
```

---

## 🔐 Security Testing

```typescript
describe('Security Tests', () => {
  it('sanitizes user input', () => {
    const { container } = render(<SearchInput />);
    const input = screen.getByRole('textbox');
    
    // Try XSS attack
    fireEvent.change(input, { target: { value: '<script>alert("xss")</script>' } });
    
    // Verify script not executed
    expect(container.innerHTML).not.toContain('<script>');
  });

  it('prevents CSRF attacks', async () => {
    // Verify CSRF tokens in forms
    render(<GovernanceForm />);
    const form = screen.getByRole('form');
    expect(form).toHaveAttribute('data-csrf-token');
  });
});
```

---

## 🎯 Testing Checklist

### Before Each Release

- [ ] All unit tests pass: `npm test`
- [ ] Integration tests pass
- [ ] E2E tests pass: `npm run test:e2e`
- [ ] Accessibility audit clean: `npm run test:a11y`
- [ ] Visual regression tests pass
- [ ] Performance benchmarks met
- [ ] Security tests pass
- [ ] Manual smoke test on staging
- [ ] Cross-browser testing (Chrome, Firefox, Safari)
- [ ] Mobile testing (iOS, Android)
- [ ] PWA functionality verified

---

## 📝 Test Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:e2e": "playwright test",
    "test:a11y": "jest --testMatch='**/*.a11y.test.ts'",
    "test:all": "npm run test && npm run test:e2e"
  }
}
```

---

## 🐛 Debugging Tests

### Jest Debug

```bash
# Run single test
npm test -- TokenBalance.test.tsx

# Watch mode
npm test -- --watch

# Debug in VS Code
# Add breakpoint, press F5
```

### Playwright Debug

```bash
# Run with UI
npx playwright test --ui

# Debug mode
npx playwright test --debug

# Generate test
npx playwright codegen http://localhost:3000
```

---

## 📊 Coverage Goals

- **Unit Tests**: 80%+ coverage
- **Integration Tests**: Key user flows covered
- **E2E Tests**: Critical paths tested
- **Accessibility**: WCAG AA compliance

Run coverage report:
```bash
npm run test:coverage
```

View report:
```bash
open coverage/lcov-report/index.html
```

---

## 🎓 Best Practices

1. **AAA Pattern**: Arrange, Act, Assert
2. **One Assertion**: One test, one thing
3. **Descriptive Names**: Test name = documentation
4. **Mock External Calls**: Don't hit real APIs
5. **Fast Tests**: Keep tests under 5s each
6. **Deterministic**: No flaky tests
7. **Isolated**: Tests don't depend on each other
8. **Readable**: Anyone can understand test

---

## 🚀 Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm ci
      - run: npm run test:all
      - run: npm run test:coverage
      - uses: codecov/codecov-action@v3
```

---

**Happy Testing! 🧪**

*"Tests are the safety net that lets you refactor with confidence."*
