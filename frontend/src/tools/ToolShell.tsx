/**
 * ToolShell - Shared layout wrapper for tool components.
 *
 * Provides:
 * - Consistent styling and layout
 * - Error boundary for tool failures
 * - Loading states
 * - Navigation actions
 */

import {
  Component,
  Suspense,
  type ReactNode,
  type ErrorInfo,
  type ComponentType,
} from 'react';
import type { ToolComponentProps, ToolMetadata } from './types';

interface ToolShellProps {
  /** Tool metadata */
  metadata: ToolMetadata;
  /** The tool component to render */
  component: ComponentType<ToolComponentProps>;
  /** Props to pass to the tool component */
  componentProps: ToolComponentProps;
  /** Custom loading fallback */
  loadingFallback?: ReactNode;
  /** Custom error fallback */
  errorFallback?: (error: Error, reset: () => void) => ReactNode;
  /** Navigation actions */
  onBack?: () => void;
  onNext?: () => void;
  /** Labels for navigation buttons */
  backLabel?: string;
  nextLabel?: string;
  /** Whether to show navigation buttons */
  showNavigation?: boolean;
}

interface ToolShellState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Default loading spinner component.
 */
function DefaultLoadingFallback() {
  return (
    <div className="tool-shell-loading">
      <span className="spinner" />
      <p>Loading tool...</p>
    </div>
  );
}

/**
 * Default error fallback component.
 */
function DefaultErrorFallback({
  error,
  toolName,
  onReset,
}: {
  error: Error;
  toolName: string;
  onReset: () => void;
}) {
  return (
    <div className="tool-shell-error" role="alert">
      <h3>Error in {toolName}</h3>
      <p>{error.message}</p>
      <button type="button" onClick={onReset} className="btn btn-secondary">
        Try Again
      </button>
    </div>
  );
}

/**
 * Error boundary wrapper for tool components.
 */
class ToolErrorBoundary extends Component<
  {
    children: ReactNode;
    toolName: string;
    onReset?: () => void;
    fallback?: (error: Error, reset: () => void) => ReactNode;
  },
  ToolShellState
> {
  constructor(props: {
    children: ReactNode;
    toolName: string;
    onReset?: () => void;
    fallback?: (error: Error, reset: () => void) => ReactNode;
  }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ToolShellState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`Tool error in ${this.props.toolName}:`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleReset);
      }
      return (
        <DefaultErrorFallback
          error={this.state.error}
          toolName={this.props.toolName}
          onReset={this.handleReset}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * ToolShell component for wrapping tool components with consistent UI.
 *
 * @example
 * ```tsx
 * <ToolShell
 *   metadata={tool.metadata}
 *   component={tool.component}
 *   componentProps={props}
 *   onBack={() => setStep(step - 1)}
 *   onNext={() => setStep(step + 1)}
 * />
 * ```
 */
export function ToolShell({
  metadata,
  component: ToolComponent,
  componentProps,
  loadingFallback,
  errorFallback,
  onBack,
  onNext,
  backLabel = 'Back',
  nextLabel = 'Continue',
  showNavigation = true,
}: ToolShellProps) {
  const handleComplete = () => {
    componentProps.onComplete?.();
    onNext?.();
  };

  const enhancedProps: ToolComponentProps = {
    ...componentProps,
    onComplete: handleComplete,
    onNavigate: componentProps.onNavigate,
  };

  return (
    <div className="tool-shell" data-tool-id={metadata.id}>
      <ToolErrorBoundary
        toolName={metadata.name}
        fallback={errorFallback}
      >
        <Suspense fallback={loadingFallback ?? <DefaultLoadingFallback />}>
          <ToolComponent {...enhancedProps} />
        </Suspense>
      </ToolErrorBoundary>

      {showNavigation && (onBack || onNext) && (
        <div className="wizard-actions">
          {onBack && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onBack}
            >
              {backLabel}
            </button>
          )}
          {onNext && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNext}
            >
              {nextLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Simplified tool renderer that just wraps with Suspense and error boundary.
 *
 * Use this when you don't need the full ToolShell wrapper.
 */
export function ToolRenderer({
  component: ToolComponent,
  componentProps,
  toolName = 'Tool',
  loadingFallback,
}: {
  component: ComponentType<ToolComponentProps>;
  componentProps: ToolComponentProps;
  toolName?: string;
  loadingFallback?: ReactNode;
}) {
  return (
    <ToolErrorBoundary toolName={toolName}>
      <Suspense fallback={loadingFallback ?? <DefaultLoadingFallback />}>
        <ToolComponent {...componentProps} />
      </Suspense>
    </ToolErrorBoundary>
  );
}

export default ToolShell;
