import os
import datetime
import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

class DICOMHandler:
    def __init__(self, storage_folder):
        self.storage_folder = storage_folder
        if not os.path.exists(self.storage_folder):
            os.makedirs(self.storage_folder)
            os.chmod(self.storage_folder, 0o700)

    def save_as_dicom(self, image_array, metadata, motor_positions):
        try:
            angle_m1 = motor_positions.get('m1', 0)
            angle_m2 = motor_positions.get('m2', 0)

            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.7'
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.ImplementationClassUID = generate_uid()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

            ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
            ds.PatientName = metadata.get('patient_name', 'Anonymous')
            ds.PatientID = metadata.get('patient_id', '000000')
            ds.PatientSex = metadata.get('patient_sex', '')
            patient_age = metadata.get('patient_age', '')
            if patient_age:
                try:
                    age_int = int(float(patient_age))
                    ds.PatientAge = f"{age_int:03d}Y"
                except:
                    pass
            ds.StudyDate = datetime.datetime.now().strftime('%Y%m%d')
            ds.StudyTime = datetime.datetime.now().strftime('%H%M%S')
            ds.Modality = 'OT'

            # Custom Data
            ds.ImageComments = f"M1_Angle:{angle_m1:.2f}, M2_Angle:{angle_m2:.2f}"
            block = ds.private_block(0x0019, "RoboticCamera", create=True)
            block.add_new(0x01, 'DS', str(round(angle_m1, 2)))
            block.add_new(0x02, 'DS', str(round(angle_m2, 2)))

            ds.SamplesPerPixel = 3
            ds.PhotometricInterpretation = "RGB"
            ds.PlanarConfiguration = 0
            ds.Rows = image_array.shape[0]
            ds.Columns = image_array.shape[1]
            ds.BitsAllocated = 8
            ds.BitsStored = 8
            ds.HighBit = 7
            ds.PixelRepresentation = 0
            ds.PixelData = image_array.tobytes()
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID

            safe_id = secure_filename(ds.PatientID)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_id}_{timestamp}.dcm"
            filepath = os.path.join(self.storage_folder, filename)
            ds.save_as(filepath)
            logger.info(f"DICOM saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving DICOM: {e}")
            raise