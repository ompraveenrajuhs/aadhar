package com.aadhar;

public class AadhaarValidator {

    public boolean isValid(String aadhaarNumber) {
        if (aadhaarNumber == null || !aadhaarNumber.matches("\\d{12}")) {
            return false;
        }

        int sum = 0;
        for (int i = 0; i < aadhaarNumber.length(); i++) {
            sum += Character.getNumericValue(aadhaarNumber.charAt(i));
        }

        return sum % 10 == 0;
    }

    public String mask(String aadhaarNumber) {
        if (aadhaarNumber == null || aadhaarNumber.length() < 4) {
            throw new IllegalArgumentException("Aadhaar must have at least 4 characters");
        }

        String visiblePart = aadhaarNumber.substring(aadhaarNumber.length() - 4);
        return "XXXXXXXX" + visiblePart;
    }

    public boolean isMasked(String aadhaarNumber) {
        return aadhaarNumber != null && aadhaarNumber.matches("X{8}\\d{4}");
    }
}
