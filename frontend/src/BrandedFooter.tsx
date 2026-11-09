import './BrandedFooter.css';

type BrandedFooterProps = {
  versionLabel: string;
};

export function BrandedFooter({ versionLabel }: BrandedFooterProps) {
  return (
    <footer className="veridian-branded-footer">
      <div className="veridian-branded-footer__grid">
        <div className="veridian-branded-footer__logo-area">
          <img
            src="/branding/sighthill-associates-logo.jpg"
            alt="Sighthill Associates, Incorporated"
            className="veridian-branded-footer__sighthill"
          />
        </div>

        <div className="veridian-branded-footer__credits">
          <small className="veridian-branded-footer__version">
            {versionLabel}
          </small>
          <small>
            © 2026 Sighthill Associates, Inc. All Rights Reserved.
          </small>
          <small>
            Development by PA - Code Wrangler
          </small>
          <small>
            Powered by ChatGPT, an AI assistant by OpenAI.
          </small>
        </div>

        <div className="veridian-branded-footer__logo-area">
          <img
            src="/branding/veridian-code-wrangler-logo.png"
            alt="VERIDIAN Code Wrangler development logo"
            className="veridian-branded-footer__wrangler"
          />
        </div>
      </div>

      <p className="veridian-branded-footer__tagline">
        VERIDIAN • Every Record. Every Decision. Every Step.
      </p>
      <p className="veridian-branded-footer__warning">
        Sandbox signing tests only; production signing and payment
        verification remain pending.
      </p>
    </footer>
  );
}
