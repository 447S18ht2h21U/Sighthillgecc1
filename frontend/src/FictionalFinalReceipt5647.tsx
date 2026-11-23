import { useState } from 'react';
import {
  readFictionalInspection5645,
  readFictionalReview5645
} from './FictionalInspectionScenario5645';

const PRICE = 13500;
const DEPOSIT = 6750;
const FINAL_PAYMENT = 6750;

const dollars = (value: number) =>
  value.toLocaleString('en-US', {
    style: 'currency', currency: 'USD'
  });

type PaymentDetails = {
  date: string;
  method: string;
  reference: string;
};

const blankPayment = (): PaymentDetails => ({
  date: '', method: '', reference: ''
});

function PaymentFields({
  title, payment, setPayment
}: {
  title: string;
  payment: PaymentDetails;
  setPayment: (next: PaymentDetails) => void;
}) {
  return <fieldset style={{
    marginBottom:'14px',padding:'12px',
    border:'1px solid #D7E3E7'
  }}>
    <legend><strong>{title}</strong></legend>
    <p className="muted">
      Fictional payment details only. Do not enter real banking information.
    </p>
    <label style={{display:'block',marginBottom:'10px'}}>
      Hypothetical payment date
      <input type="date" value={payment.date}
        onChange={e=>setPayment({
          ...payment,date:e.target.value
        })}/>
    </label>
    <label style={{display:'block',marginBottom:'10px'}}>
      Hypothetical payment method
      <select value={payment.method}
        onChange={e=>setPayment({
          ...payment,method:e.target.value
        })}>
        <option value="">Choose fictional method</option>
        <option value="Fictional bank transfer">Fictional bank transfer</option>
        <option value="Fictional cashier's check">Fictional cashier's check</option>
        <option value="Fictional money order">Fictional money order</option>
      </select>
    </label>
    <label style={{display:'block'}}>
      Fictional reference (not a bank confirmation)
      <input value={payment.reference}
        maxLength={100}
        placeholder="Example: TEST-104-DEPOSIT"
        onChange={e=>setPayment({
          ...payment,reference:e.target.value
        })}/>
    </label>
  </fieldset>;
}

export function FictionalFinalReceipt5647() {
  const [deposit,setDeposit] = useState<PaymentDetails>(blankPayment);
  const [finalPayment,setFinalPayment] =
    useState<PaymentDetails>(blankPayment);
  const [reviewVersion,setReviewVersion] = useState(0);
  const [prepared,setPrepared] = useState(false);
  const [delivery,setDelivery] = useState(false);
  const [certificate,setCertificate] = useState(false);
  const [acceptance,setAcceptance] = useState(false);
  const [receiptShown,setReceiptShown] = useState(false);

  // Re-read browser-local practice evidence on each refresh.
  // It is untrusted simulation data, never operational authority.
  void reviewVersion;
  const inspection = readFictionalInspection5645();
  const review = readFictionalReview5645();
  const practiceAccepted =
    Boolean(inspection) &&
    review?.decision === 'practice-accepted' &&
    inspection?.findings.every(f=>f==='pass') === true;

  const paymentDetailsValid = [deposit,finalPayment].every(p =>
    /^\d{4}-\d{2}-\d{2}$/.test(p.date) &&
    Number.isFinite(Date.parse(p.date)) &&
    Boolean(p.method) &&
    p.reference.trim().length >= 5
  );

  const canPrepare = practiceAccepted && paymentDetailsValid;
  const complete = prepared && delivery && certificate && acceptance &&
    canPrepare;

  const refresh = () => {
    setReviewVersion(v=>v+1);
    setPrepared(false);
    setReceiptShown(false);
    setDelivery(false);
    setCertificate(false);
    setAcceptance(false);
  };

  const reset = () => {
    setDeposit(blankPayment());
    setFinalPayment(blankPayment());
    refresh();
  };

  return <section style={{
    border:'2px dashed #087F75',
    borderRadius:'6px',padding:'18px',
    margin:'18px 0'
  }}>
    <h4>Project 104 - Fictional Final Receipt and Completion</h4>
    <p><strong>
      SIMULATION ONLY - NOT A RECEIPT FOR ACTUAL PAYMENT
    </strong></p>
    <p>This practice demonstrates the customer payment, final Receipt,
      and project completion sequence. Nothing is transmitted or saved
      as operational financial or project evidence.</p>

    <button type="button" className="quiet" onClick={refresh}>
      Refresh fictional review
    </button>

    <p><strong>Fictional inspection review:</strong>{' '}
      {practiceAccepted
        ? 'Practice accepted'
        : 'Not available or not accepted'}
    </p>

    <h4>1. Hypothetical full payment</h4>
    <p>Approved project price: <strong>{dollars(PRICE)}</strong></p>
    <p>Hypothetical initial deposit: <strong>{dollars(DEPOSIT)}</strong></p>
    <p>Hypothetical final payment: <strong>
      {dollars(FINAL_PAYMENT)}
    </strong></p>
    <p>Hypothetical remaining balance: <strong>
      {dollars(PRICE-DEPOSIT-FINAL_PAYMENT)}
    </strong></p>

    <PaymentFields title="Fictional deposit - $6,750"
      payment={deposit}
      setPayment={p=>{
        setDeposit(p);setPrepared(false);setReceiptShown(false);
        setDelivery(false);setAcceptance(false);
      }}/>

    <PaymentFields title="Fictional final payment - $6,750"
      payment={finalPayment}
      setPayment={p=>{
        setFinalPayment(p);setPrepared(false);setReceiptShown(false);
        setDelivery(false);setAcceptance(false);
      }}/>

    <button type="button"
      disabled={!canPrepare}
      onClick={()=>{
        setPrepared(true);
        setReceiptShown(true);
        setDelivery(false);
        setAcceptance(false);
      }}>
      Prepare fictional final Receipt
    </button>

    {receiptShown && prepared && canPrepare && (
      <section style={{
        border:'2px solid #142B3B',
        padding:'16px',marginTop:'16px',
        background:'#F7F8F5'
      }}>
        <p><strong>
          FICTIONAL PREVIEW - DO NOT ISSUE OR SEND
        </strong></p>
        <h4>Green Energy Contracting Corporation</h4>
        <h4>Final Receipt - Fictional Project 104</h4>
        <p>Project: 104-SA-2026-11-22</p>
        <p>Approved MSR: 4.0</p>
        <p>Approved total: {dollars(PRICE)}</p>
        <table>
          <thead><tr>
            <th>Hypothetical payment</th>
            <th>Amount</th>
            <th>Date</th>
            <th>Method and reference</th>
          </tr></thead>
          <tbody>
            <tr><td>Deposit</td>
              <td>{dollars(DEPOSIT)}</td>
              <td>{deposit.date}</td>
              <td>{deposit.method} - {deposit.reference}</td>
            </tr>
            <tr><td>Final payment</td>
              <td>{dollars(FINAL_PAYMENT)}</td>
              <td>{finalPayment.date}</td>
              <td>{finalPayment.method} - {finalPayment.reference}</td>
            </tr>
          </tbody>
        </table>
        <p>Total hypothetical payments: <strong>
          {dollars(DEPOSIT+FINAL_PAYMENT)}
        </strong></p>
        <p>Hypothetical remaining balance: <strong>$0.00</strong></p>
        <p><strong>
          NOT PAID IN FACT. NO FUNDS OR CUSTOMER RECEIPT VERIFIED.
          NOT VALID FOR CUSTOMER DELIVERY OR ACCOUNTING.
        </strong></p>
      </section>
    )}

    <h4>2. Fictional delivery and certificate checks</h4>
    <label style={{
      display:'flex',gap:'10px',alignItems:'flex-start',
      marginBottom:'12px'
    }}>
      <input type="checkbox" checked={delivery}
        disabled={!prepared || !canPrepare}
        style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
        onChange={e=>setDelivery(e.target.checked)}/>
      <span>Simulate customer email delivery of the fictional
        Receipt. No email was actually sent.</span>
    </label>
    <label style={{
      display:'flex',gap:'10px',alignItems:'flex-start',
      marginBottom:'12px'
    }}>
      <input type="checkbox" checked={certificate}
        disabled={!prepared || !canPrepare}
        style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
        onChange={e=>setCertificate(e.target.checked)}/>
      <span>Simulate a completed Completion Certificate review.
        No certificate was issued or provider-verified by this practice.</span>
    </label>
    <label style={{
      display:'flex',gap:'10px',alignItems:'flex-start',
      marginBottom:'12px'
    }}>
      <input type="checkbox" checked={acceptance}
        disabled={!prepared || !canPrepare}
        style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
        onChange={e=>setAcceptance(e.target.checked)}/>
      <span>I understand this exercise creates no actual payment,
        customer Receipt, installation approval, or project completion.</span>
    </label>

    <h4>3. Fictional project completion assessment</h4>
    {complete ? (
      <p role="status"><strong>
        FICTIONAL PROJECT 104 LIFECYCLE PRACTICE COMPLETE
      </strong>{' - '}Approved MSR, sandbox commercial signing,
      hypothetical payment, installation practice, fictional
      inspection review, Receipt preview and delivery/certificate
      simulations have been demonstrated separately.
      No operational completion has been authorized.</p>
    ) : (
      <p role="status">
        Practice completion pending. An accepted fictional inspection
        review, complete hypothetical payment details, Receipt preview,
        and all three fictional confirmations are required.
      </p>
    )}

    <button type="button" className="quiet" onClick={reset}>
      Reset fictional Receipt practice
    </button>

    <p className="muted">
      All inputs in this section are transient browser state.
      They are not persisted financial records. The separate
      operational Customer Payment Evidence, Independent Installation
      Inspection Review, and Project Completion Review safeguards
      remain unchanged.
    </p>
  </section>;
}
