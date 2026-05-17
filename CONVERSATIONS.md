# Sample Conversations

---

## 1. Successful End-to-End Payment

> Messy natural language throughout. User pays partial amount.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  yeah my account number is ACC 1001 I think

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  it's Nithin, Nithin Jain

Agent: Thank you. To complete verification, please provide one of:
       your date of birth, the last 4 digits of your Aadhaar, or
       your pincode.

User:  I was born on 14th May 1990

Agent: Identity verified! ✓

       Your outstanding balance is ₹1,250.75. How much would you
       like to pay today? You can pay the full amount or a partial
       amount.

User:  can I do 500 for now?

Agent: To process your payment of ₹500.00, I'll need your card
       details. Please share your card number, CVV, expiry date,
       and the name as it appears on your card.

User:  the card number is 4532 0151 1283 0366, CVV is one two three,
       expires December 2027, name Nithin Jain

Agent: Payment successful! ✓

       Here's a summary of your transaction:
         • Account ID    : ACC1001
         • Amount paid   : ₹500.00
         • Transaction ID: txn_1762510325322_l1fl4oy

       Your payment has been processed successfully. Please keep
       your transaction ID for reference. Thank you and have a
       great day!
```

---

## 2. Verification Failure — User Exhausts All Retries

> User consistently provides wrong information across 3 attempts.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  ACC1001

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  john doe

Agent: To complete verification, please provide one of: your date
       of birth, the last 4 digits of your Aadhaar, or your pincode.

User:  1990-05-14

Agent: The name you entered doesn't match our records. Please
       re-enter your full legal name with correct capitalisation
       (e.g. 'Nithin Jain') along with your verification factor.
       You have 2 attempt(s) remaining.

User:  nithin jain and DOB 1990-05-14

Agent: The name you entered doesn't match our records. Please
       re-enter your full legal name with correct capitalisation
       (e.g. 'Nithin Jain') along with your verification factor.
       You have 1 attempt(s) remaining.

User:  Nithin Jain and pincode 999999

Agent: The verification factor you provided doesn't match our
       records. Please re-enter your name and try a different
       factor (date of birth, Aadhaar last 4 digits, or pincode).
       You have 0 attempt(s) remaining.

       [verification exhausted on this attempt]

Agent: We were unable to verify your identity after multiple
       attempts. For your security, this session has been closed.
       Please contact customer support for further assistance.
```

---

## 3. Payment Failure — Invalid Card, Then Success

> User provides an invalid card number. Agent re-collects and retries.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  ACC1002

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  Rajarajeswari Balasubramaniam, DOB 1985-11-23

Agent: Identity verified! ✓

       Your outstanding balance is ₹540.00. How much would you
       like to pay today?

User:  just clear the full amount

Agent: To process your payment of ₹540.00, I'll need your card
       details. Please share your card number, CVV, expiry date,
       and the name as it appears on your card.

User:  card 1234567890123456 CVV 123 expiry 12/2027 Raja

Agent: Card number appears to be invalid. Please double-check it.
       Please re-enter the correct details.

User:  sorry, it's 5425 2334 3010 9903 CVV 123 expiry 12/2027
       Rajarajeswari Balasubramaniam

Agent: Payment successful! ✓

       Here's a summary of your transaction:
         • Account ID    : ACC1002
         • Amount paid   : ₹540.00
         • Transaction ID: txn_1762510325322_ab3cd4e

       Your payment has been processed successfully. Please keep
       your transaction ID for reference. Thank you and have a
       great day!
```

---

## 4. Edge Case — Zero Balance Account

> Account has no outstanding balance. Conversation closes after verification.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  account id acc 1003

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  Priya Agarwal, pincode 4 0 0 0 0 3

Agent: Identity verified! ✓

       Your outstanding balance is ₹0.00. There's nothing to pay
       at this time. Have a great day!
```

---

## 5. Edge Case — Leap Year DOB (ACC1004)

> Rahul Mehta's DOB is 1988-02-29 — a valid leap year date.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  ACC1004

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  Rahul Mehta, born on 29th February 1988

Agent: Identity verified! ✓

       Your outstanding balance is ₹3,200.50. How much would you
       like to pay today?
```

---

## 5b. Payment Failure — Expired Card (Client-Side Rejection)

> Card is expired — caught locally before hitting the API.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  ACC1001

Agent: To verify your identity, I'll need your full name and one of
       the following: your date of birth, the last 4 digits of your
       Aadhaar, or your pincode.

User:  Nithin Jain, DOB 1990-05-14

Agent: Identity verified! ✓

       Your outstanding balance is ₹1,250.75. How much would you
       like to pay today?

User:  500

Agent: To process your payment of ₹500.00, I'll need your card
       details. Please share your card number, CVV, expiry date,
       and the name as it appears on your card.

User:  card 4532015112830366 CVV 123 expiry 06/2023 Nithin Jain

Agent: This card has already expired. Please re-enter the correct
       details.

User:  same card but expiry is 12/2027

Agent: Payment successful! ✓

       Here's a summary of your transaction:
         • Account ID    : ACC1001
         • Amount paid   : ₹500.00
         • Transaction ID: txn_1762510325322_l1fl4oy

       Your payment has been processed successfully. Please keep
       your transaction ID for reference. Thank you and have a
       great day!
```

---

## 6. Edge Case — User Volunteers Info Out of Order

> User provides their name before being asked, while giving account ID.

```
Agent: Hello! I'm here to help you with your payment. To get started,
       could you please share your account ID?

User:  My name is Nithin Jain and my account is ACC1001

Agent: Thank you. To complete verification, please provide one of:
       your date of birth, the last 4 digits of your Aadhaar, or
       your pincode.

[Name was captured automatically — user is not asked for it again]

User:  aadhaar last four is 4321

Agent: Identity verified! ✓

       Your outstanding balance is ₹1,250.75. How much would you
       like to pay today?
```
